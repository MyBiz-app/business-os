import { useEffect, useRef, useState } from "react";
import { Animated, Easing, Platform, StyleSheet, View } from "react-native";

import { useTheme } from "../providers/theme-provider";
import { useReducedMotion } from "./motion";

const native = Platform.OS !== "web";

// The mark on a 64 x 64 grid (the same geometry as packages/brand): an M drawn as a network of
// five nodes. Drawn from plain views so the apps need no vector library.
const TILE = 96;
const UNIT = TILE / 64;
const POINTS: [number, number][] = [
  [18, 43],
  [18, 22],
  [32, 36],
  [46, 22],
  [46, 43],
];
const TILE_COLOR = "#3B82F6";
const LINE_WIDTH = 5.5 * UNIT;
const NODE = 8.4 * UNIT;

/** Set once the launch screen has played, so it shows on the first open only, not on every remount. */
let played = false;

function Segment({ from, to }: { from: [number, number]; to: [number, number] }) {
  const dx = (to[0] - from[0]) * UNIT;
  const dy = (to[1] - from[1]) * UNIT;
  const length = Math.hypot(dx, dy);
  const cx = ((from[0] + to[0]) / 2) * UNIT;
  const cy = ((from[1] + to[1]) / 2) * UNIT;
  return (
    <View
      style={{
        position: "absolute",
        width: length,
        height: LINE_WIDTH,
        borderRadius: LINE_WIDTH / 2,
        backgroundColor: "#fff",
        left: cx - length / 2,
        top: cy - LINE_WIDTH / 2,
        transform: [{ rotate: `${Math.atan2(dy, dx)}rad` }],
      }}
    />
  );
}

/** The MyBiz mark: gradient-blue tile with the networked M, in white. */
export function LogoMark() {
  return (
    <View style={styles.tile} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      {POINTS.slice(1).map((p, i) => (
        <Segment key={i} from={POINTS[i]} to={p} />
      ))}
      {POINTS.map(([x, y]) => (
        <View
          key={`${x}-${y}`}
          style={{
            position: "absolute",
            width: NODE,
            height: NODE,
            borderRadius: NODE / 2,
            backgroundColor: "#fff",
            left: x * UNIT - NODE / 2,
            top: y * UNIT - NODE / 2,
          }}
        />
      ))}
    </View>
  );
}

/**
 * The launch screen every app shows on open: the mark pops in and breathes over the app's
 * background, then the layer fades out and unmounts. It sits on top of the already-rendering app
 * (nothing waits for it) and ignores touches. Reduced motion: a short plain fade.
 */
export function LaunchSplash() {
  const { palette } = useTheme();
  const reduced = useReducedMotion();
  const [visible, setVisible] = useState(!played);
  const pop = useRef(new Animated.Value(reduced ? 1 : 0)).current;
  const fade = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (!visible) return;
    played = true;
    const intro = reduced
      ? Animated.delay(350)
      : Animated.sequence([
          Animated.spring(pop, { toValue: 1, friction: 6, tension: 80, useNativeDriver: native }),
          Animated.timing(pop, { toValue: 1.06, duration: 350, easing: Easing.inOut(Easing.quad), useNativeDriver: native }),
          Animated.timing(pop, { toValue: 1, duration: 350, easing: Easing.inOut(Easing.quad), useNativeDriver: native }),
        ]);
    Animated.sequence([intro, Animated.timing(fade, { toValue: 0, duration: 400, useNativeDriver: native })]).start(() =>
      setVisible(false),
    );
    // Plays once on mount; later changes of the reduced-motion setting do not restart it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!visible) return null;
  return (
    <Animated.View pointerEvents="none" style={[styles.layer, { backgroundColor: palette.background, opacity: fade }]}>
      <Animated.View
        style={{
          opacity: pop.interpolate({ inputRange: [0, 0.6, 1], outputRange: [0, 1, 1], extrapolate: "clamp" }),
          transform: [{ scale: pop.interpolate({ inputRange: [0, 1], outputRange: [0.6, 1] }) }],
        }}
      >
        <LogoMark />
      </Animated.View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  layer: { position: "absolute", top: 0, bottom: 0, start: 0, end: 0, alignItems: "center", justifyContent: "center", zIndex: 9999, elevation: 9999 },
  tile: { width: TILE, height: TILE, borderRadius: 22, backgroundColor: TILE_COLOR, overflow: "hidden" },
});
