import { StyleSheet } from "react-native";
import { Text } from "./text";

import { PressableScale } from "./motion";
import { haptics } from "../lib/haptics";
import { font } from "../lib/typography";
import type { Palette } from "../lib/theme";
import { radius } from "../lib/theme";

type Props = {
  label: string;
  sublabel?: string;
  selected: boolean;
  onPress: () => void;
  palette: Palette;
  accessibilityLabel?: string;
  role?: "radio" | "checkbox" | "tab" | "button";
};

/** A selectable pill: one choice in a row (staff, time, day…). */
export function Chip({ label, sublabel, selected, onPress, palette, accessibilityLabel, role = "radio" }: Props) {
  return (
    <PressableScale
      role={role}
      aria-checked={role === "radio" || role === "checkbox" ? selected : undefined}
      aria-selected={role === "tab" ? selected : undefined}
      accessibilityLabel={accessibilityLabel ?? label}
      onPress={() => {
        if (!selected) haptics.select();
        onPress();
      }}
      style={[
        local.chip,
        selected
          ? { backgroundColor: palette.primary, borderColor: palette.primary }
          : { backgroundColor: palette.surface, borderColor: palette.border },
      ]}
    >
      <Text style={[local.label, { color: selected ? palette.onPrimary : palette.foreground }]}>{label}</Text>
      {sublabel ? <Text style={[local.sub, { color: selected ? palette.onPrimary : palette.muted }]}>{sublabel}</Text> : null}
    </PressableScale>
  );
}

const local = StyleSheet.create({
  chip: { borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: 16, paddingVertical: 10, alignItems: "center", justifyContent: "center", minWidth: 64, minHeight: 44 },
  label: { fontSize: 15, ...font.semibold, fontVariant: ["tabular-nums"] },
  sub: { fontSize: 12, ...font.medium },
});
