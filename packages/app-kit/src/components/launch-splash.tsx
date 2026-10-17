import { useEffect, useRef, useState } from "react";
import { Animated, Easing, Platform, StyleSheet, View } from "react-native";

import { tint } from "../lib/brand";
import { colors } from "../lib/theme";
import { useTheme } from "../providers/theme-provider";
import { AuthBackdrop } from "./auth-backdrop";
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
// The mark is the same in both themes: white strokes on the brand blue tile.
const TILE_COLOR = colors.dark.primary;
const MARK_COLOR = colors.light.surface;
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
        backgroundColor: MARK_COLOR,
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
            backgroundColor: MARK_COLOR,
            left: x * UNIT - NODE / 2,
            top: y * UNIT - NODE / 2,
          }}
        />
      ))}
    </View>
  );
}

/**
 * The mark with depth: a soft halo, a shadow under the tile, a slow tilt in perspective and a
 * light that sweeps across it. `size` scales the whole thing (the tile is 96 at size 1).
 * Reduced motion: the mark stays still.
 */
export function DepthLogo({ size = 1, still = false }: { size?: number; still?: boolean }) {
  const { palette } = useTheme();
  const reducedMotion = useReducedMotion();
  const reduced = reducedMotion || still;
  const drift = useRef(new Animated.Value(0)).current;
  const sweep = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (reduced) return;
    const tilt = Animated.loop(
      Animated.sequence([
        Animated.timing(drift, { toValue: 1, duration: 2600, easing: Easing.inOut(Easing.sin), useNativeDriver: native }),
        Animated.timing(drift, { toValue: 0, duration: 2600, easing: Easing.inOut(Easing.sin), useNativeDriver: native }),
      ]),
    );
    const light = Animated.loop(
      Animated.sequence([
        Animated.delay(1400),
        Animated.timing(sweep, { toValue: 1, duration: 900, easing: Easing.inOut(Easing.quad), useNativeDriver: native }),
        Animated.timing(sweep, { toValue: 0, duration: 0, useNativeDriver: native }),
      ]),
    );
    tilt.start();
    light.start();
    return () => {
      tilt.stop();
      light.stop();
    };
  }, [drift, sweep, reduced]);

  const box = TILE * size;
  return (
    <View style={{ width: box * 1.7, height: box * 1.7, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          position: "absolute",
          width: box * 1.6,
          height: box * 1.6,
          borderRadius: box,
          backgroundColor: tint(palette.primary, 0.14),
        }}
      />
      <View
        style={{
          position: "absolute",
          width: box * 1.28,
          height: box * 1.28,
          borderRadius: box,
          backgroundColor: tint(palette.accent, 0.12),
        }}
      />
      <Animated.View
        style={{
          width: box,
          height: box,
          boxShadow: `0px ${14 * size}px ${34 * size}px ${tint(colors.light.primary, 0.45)}`,
          borderRadius: 22 * size,
          transform: [
            { perspective: 700 },
            { rotateY: drift.interpolate({ inputRange: [0, 1], outputRange: ["-14deg", "14deg"] }) },
            { rotateX: drift.interpolate({ inputRange: [0, 1], outputRange: ["8deg", "-8deg"] }) },
          ],
        }}
      >
        <View style={{ width: TILE, height: TILE, transform: [{ scale: size }], transformOrigin: "top left" }}>
          <LogoMark />
        </View>
        <View pointerEvents="none" style={{ position: "absolute", top: 0, bottom: 0, start: 0, end: 0, borderRadius: 22 * size, overflow: "hidden" }}>
          <Animated.View
            style={{
              position: "absolute",
              top: -box * 0.2,
              width: box * 0.28,
              height: box * 1.4,
              backgroundColor: "rgba(255,255,255,0.35)",
              transform: [
                { translateX: sweep.interpolate({ inputRange: [0, 1], outputRange: [-box * 0.4, box * 1.2] }) },
                { rotate: "18deg" },
              ],
            }}
          />
        </View>
      </Animated.View>
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
      <AuthBackdrop />
      <Animated.View
        style={{
          opacity: pop.interpolate({ inputRange: [0, 0.6, 1], outputRange: [0, 1, 1], extrapolate: "clamp" }),
          transform: [{ scale: pop.interpolate({ inputRange: [0, 1], outputRange: [0.6, 1] }) }],
        }}
      >
        <DepthLogo size={1.15} />
      </Animated.View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  layer: { position: "absolute", top: 0, bottom: 0, start: 0, end: 0, alignItems: "center", justifyContent: "center", zIndex: 9999, elevation: 9999 },
  tile: { width: TILE, height: TILE, borderRadius: 22, backgroundColor: TILE_COLOR, overflow: "hidden" },
});
