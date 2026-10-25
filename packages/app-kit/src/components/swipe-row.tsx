import Ionicons from "@expo/vector-icons/Ionicons";
import { type ComponentProps, useMemo, useRef } from "react";
import { Animated, I18nManager, PanResponder, Platform, StyleSheet, View } from "react-native";

import { haptics } from "../lib/haptics";
import { commits, isSideways, pullDistance, SWIPE_COMMIT } from "../lib/swipe-rules";
import type { Palette } from "../lib/theme";
import { radius } from "../lib/theme";
import { useReducedMotion } from "./motion";
import { Text } from "./text";

const native = Platform.OS !== "web";

/**
 * Drag a row toward its trailing edge to run one action (like swiping a message in Mail). Letting go
 * past the commit distance runs `onAction` and the row springs back; a vertical scroll is left alone.
 * It is only a shortcut: every action must also be reachable with a plain button, so nobody needs
 * the gesture (switch access, screen readers).
 */
export function SwipeRow({
  label,
  icon,
  tone = "danger",
  palette,
  onAction,
  children,
}: {
  label: string;
  icon: ComponentProps<typeof Ionicons>["name"];
  tone?: "primary" | "danger";
  palette: Palette;
  onAction: () => void;
  children: React.ReactNode;
}) {
  const reduced = useReducedMotion();
  const offset = useRef(new Animated.Value(0)).current;
  const armed = useRef(false);
  const action = useRef(onAction);
  action.current = onAction;
  const color = tone === "danger" ? palette.danger : palette.primary;
  const rtl = I18nManager.isRTL;
  const sign = rtl ? -1 : 1;

  const responder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_event, g) => isSideways(g.dx, g.dy),
        onPanResponderMove: (_event, g) => {
          const distance = pullDistance(g.dx, rtl);
          offset.setValue(distance * sign);
          const now = commits(distance);
          if (now !== armed.current) {
            armed.current = now;
            haptics.select();
          }
        },
        onPanResponderRelease: (_event, g) => {
          const run = commits(pullDistance(g.dx, rtl));
          armed.current = false;
          Animated.spring(offset, { toValue: 0, speed: reduced ? 40 : 20, bounciness: 0, useNativeDriver: native }).start();
          if (run) action.current();
        },
        onPanResponderTerminate: () => {
          armed.current = false;
          Animated.spring(offset, { toValue: 0, useNativeDriver: native }).start();
        },
      }),
    [offset, reduced, rtl, sign],
  );

  return (
    <View style={local.wrap}>
      <View accessible={false} importantForAccessibility="no-hide-descendants" style={[local.behind, { backgroundColor: color }]}>
        <Ionicons name={icon} size={20} color={palette.onPrimary} />
        <Text style={[local.label, { color: palette.onPrimary }]}>{label}</Text>
      </View>
      <Animated.View {...responder.panHandlers} style={{ transform: [{ translateX: offset }], backgroundColor: palette.background }}>
        {children}
      </Animated.View>
    </View>
  );
}

const local = StyleSheet.create({
  wrap: { overflow: "hidden", borderRadius: radius.card },
  // The action sits at the leading edge, where the row has been pulled away from.
  behind: {
    position: "absolute",
    top: 0,
    bottom: 0,
    start: 0,
    width: SWIPE_COMMIT * 1.4,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  label: { fontSize: 13, fontWeight: "600" },
});
