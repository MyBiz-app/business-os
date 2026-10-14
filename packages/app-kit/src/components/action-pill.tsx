import Ionicons from "@expo/vector-icons/Ionicons";
import type { ComponentProps } from "react";
import { StyleSheet } from "react-native";

import { tint } from "../lib/brand";
import type { Palette } from "../lib/theme";
import { PressableScale } from "./motion";
import { Text } from "./text";

/** A small rounded action with an icon ("Navigate", "Add to calendar", "Cancel"). */
export function ActionPill({
  label,
  icon,
  onPress,
  palette,
  tone = "primary",
  busy,
}: {
  label: string;
  icon: ComponentProps<typeof Ionicons>["name"];
  onPress: () => void;
  palette: Palette;
  tone?: "primary" | "danger";
  busy?: boolean;
}) {
  const color = tone === "danger" ? palette.danger : palette.primary;
  return (
    <PressableScale
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ busy: !!busy, disabled: !!busy }}
      disabled={busy}
      onPress={onPress}
      style={[local.pill, { backgroundColor: tint(color, 0.12), opacity: busy ? 0.6 : 1 }]}
    >
      <Ionicons name={icon} size={16} color={color} />
      <Text style={[local.label, { color }]}>{label}</Text>
    </PressableScale>
  );
}

const local = StyleSheet.create({
  pill: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 12, minHeight: 44, borderRadius: 999 },
  label: { fontSize: 14, fontWeight: "600" },
});
