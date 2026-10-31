import { useEffect, useRef } from "react";
import { Animated, Easing, Platform, StyleSheet, View } from "react-native";

import { tint } from "../lib/brand";
import { useTheme } from "../providers/theme-provider";
import { useReducedMotion } from "./motion";

const native = Platform.OS !== "web";

const RINGS = 44;

/** A soft glow: the layers are circles that shrink one by one, so the stacked translucent
 * colors fade out smoothly toward the edge (a radial gradient from plain views, no vector or
 * gradient library). `alpha` is how strong the middle gets, as the sum of its layers (spread over them, so the steps stay too faint to see). */
export function Glow({ color, size, alpha }: { color: string; size: number; alpha: number }) {
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }} pointerEvents="none">
      {Array.from({ length: RINGS }, (_, i) => {
        const diameter = size * (1 - i / RINGS);
        return (
          <View
            key={i}
            style={{ position: "absolute", width: diameter, height: diameter, borderRadius: diameter / 2, backgroundColor: tint(color, (alpha * 18) / RINGS) }}
          />
        );
      })}
    </View>
  );
}

/** One large soft glow that drifts slowly back and forth. */
function Orb({ color, size, alpha, top, start, dx, dy, duration }: { color: string; size: number; alpha: number; top: `${number}%`; start: `${number}%`; dx: number; dy: number; duration: number }) {
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
        transform: [
          { translateX: t.interpolate({ inputRange: [0, 1], outputRange: [0, dx] }) },
          { translateY: t.interpolate({ inputRange: [0, 1], outputRange: [0, dy] }) },
        ],
      }}
    >
      <Glow color={color} size={size} alpha={alpha} />
    </Animated.View>
  );
}

/** The branded background of the sign-in, launch and lock screens: a deep base with three soft
 * glows in the brand colors that drift slowly, like the light behind frosted glass. Purely
 * decorative (hidden from screen readers, ignores touches). */
export function AuthBackdrop() {
  const { palette, scheme } = useTheme();
  const dark = scheme === "dark";
  const alpha = dark ? 0.05 : 0.026;
  return (
    <View aria-hidden style={[StyleSheet.absoluteFill, { overflow: "hidden", pointerEvents: "none" }]} importantForAccessibility="no-hide-descendants">
      <Orb color={palette.primary} alpha={alpha} size={620} top="-24%" start="-40%" dx={50} dy={36} duration={9000} />
      <Orb color={palette.ai} alpha={alpha * 0.9} size={560} top="48%" start="30%" dx={-44} dy={-34} duration={11000} />
      <Orb color={palette.accent} alpha={alpha * 0.7} size={360} top="22%" start="48%" dx={-30} dy={40} duration={8000} />
    </View>
  );
}
