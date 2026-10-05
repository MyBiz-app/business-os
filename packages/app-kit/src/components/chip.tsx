import { StyleSheet, Text } from "react-native";

import { PressableScale } from "./motion";
import { tint } from "../lib/brand";
import type { Palette } from "../lib/theme";

type Props = {
  label: string;
  sublabel?: string;
  selected: boolean;
  onPress: () => void;
  palette: Palette;
  accessibilityLabel?: string;
  role?: "radio" | "tab";
};

/** A selectable pill: one choice in a row (staff, time, day…). */
export function Chip({ label, sublabel, selected, onPress, palette, accessibilityLabel, role = "radio" }: Props) {
  return (
    <PressableScale
      role={role}
      aria-checked={role === "radio" ? selected : undefined}
      aria-selected={role === "tab" ? selected : undefined}
      accessibilityLabel={accessibilityLabel ?? label}
      onPress={onPress}
      style={[
        local.chip,
        selected
          ? { backgroundColor: palette.primary, borderColor: palette.primary, boxShadow: `0px 4px 12px ${tint(palette.primary, 0.3)}` }
          : { backgroundColor: palette.surface, borderColor: palette.border },
      ]}
    >
      <Text style={[local.label, { color: selected ? palette.onPrimary : palette.foreground }]}>{label}</Text>
      {sublabel ? <Text style={[local.sub, { color: selected ? palette.onPrimary : palette.muted }]}>{sublabel}</Text> : null}
    </PressableScale>
  );
}

const local = StyleSheet.create({
  chip: { borderWidth: 1, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 10, alignItems: "center", minWidth: 64 },
  label: { fontSize: 15, fontWeight: "700", fontVariant: ["tabular-nums"] },
  sub: { fontSize: 11, fontWeight: "600" },
});
