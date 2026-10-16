import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";

import { styles } from "@business-os/app-kit/components/ui";
import type { Palette } from "@business-os/app-kit/lib/theme";

/** A small bar chart: one bar per point, the tallest one in the primary color. Each bar reads its
 * date and value to a screen reader. */
export function TrendBars({
  points,
  label,
  value,
  empty,
  palette,
}: {
  points: { bucket: string; value: number }[];
  label: (bucket: string) => string;
  value: (value: number) => string;
  empty: string;
  palette: Palette;
}) {
  const max = Math.max(0, ...points.map((point) => point.value));
  if (points.length === 0 || max === 0) {
    return <Text style={[styles.muted, { color: palette.muted }]}>{empty}</Text>;
  }
  const best = points.reduce((top, point) => (point.value > top.value ? point : top));
  return (
    <View style={{ gap: 8 }}>
      <View
        style={{
          flexDirection: "row",
          alignItems: "flex-end",
          gap: points.length > 20 ? 2 : 4,
          height: 120,
          borderBottomWidth: 1,
          borderColor: palette.border,
        }}
      >
        {points.map((point) => (
          <View
            key={point.bucket}
            role="img"
            accessible
            accessibilityLabel={`${label(point.bucket)}: ${value(point.value)}`}
            style={{
              flex: 1,
              height: `${Math.max(2, (point.value / max) * 100)}%`,
              backgroundColor: point === best ? palette.primary : palette.border,
              borderTopLeftRadius: 4,
              borderTopRightRadius: 4,
            }}
          />
        ))}
      </View>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Text style={{ color: palette.muted, fontSize: 12 }}>{label(points[0].bucket)}</Text>
        <Text style={{ color: palette.muted, fontSize: 12 }}>{label(points[points.length - 1].bucket)}</Text>
      </View>
    </View>
  );
}
