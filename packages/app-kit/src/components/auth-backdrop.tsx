import { useEffect, useRef } from "react";
import { Animated, Easing, Platform, StyleSheet, View } from "react-native";

import { tint } from "../lib/brand";
import { useTheme } from "../providers/theme-provider";
import { useReducedMotion } from "./motion";

const native = Platform.OS !== "web";

/** One large soft circle that drifts slowly back and forth. */
function Orb({ color, size, top, start, dx, dy, duration }: { color: string; size: number; top: `${number}%`; start: `${number}%`; dx: number; dy: number; duration: number }) {
  const reduced = useReducedMotion();
  const t = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (reduced) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(t, { toValue: 1, duration, easing: Easing.inOut(Easing.sin), useNativeDriver: native }),
        Animated.timing(t, { toValue: 0, duration, easing: Easing.inOut(Easing.sin), useNativeDriver: native }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [t, reduced, duration]);
  return (
    <Animated.View
      style={{
        position: "absolute",
        top,
        start,
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: color,
        transform: [
          { translateX: t.interpolate({ inputRange: [0, 1], outputRange: [0, dx] }) },
          { translateY: t.interpolate({ inputRange: [0, 1], outputRange: [0, dy] }) },
        ],
      }}
    />
  );
}

/** The branded background of the sign-in, launch and lock screens: soft shapes in the brand
 * colors that drift slowly. Purely decorative (hidden from screen readers, ignores touches). */
export function AuthBackdrop() {
  const { palette, scheme } = useTheme();
  const strength = scheme === "dark" ? 0.3 : 0.16;
  return (
    <View pointerEvents="none" aria-hidden style={[StyleSheet.absoluteFill, { overflow: "hidden" }]} importantForAccessibility="no-hide-descendants">
      <Orb color={tint(palette.primary, strength)} size={340} top="-8%" start="-25%" dx={40} dy={30} duration={7000} />
      <Orb color={tint(palette.ai, strength * 0.9)} size={300} top="55%" start="55%" dx={-36} dy={-28} duration={8500} />
      <Orb color={tint(palette.accent, strength * 0.8)} size={220} top="30%" start="62%" dx={-24} dy={34} duration={6500} />
    </View>
  );
}
