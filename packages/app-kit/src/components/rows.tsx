import Ionicons from "@expo/vector-icons/Ionicons";
import { localeDirection, type Locale } from "@business-os/i18n";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocale } from "use-intl";

import { PressableScale } from "./motion";
import { tint } from "../lib/brand";
import { initials } from "../lib/names";
import type { Palette } from "../lib/theme";

type IconName = React.ComponentProps<typeof Ionicons>["name"];

/** "Back" points the way the reading direction goes back: right in Hebrew, left in English. */
function useBackIcon(): { back: IconName; forward: IconName } {
  const rtl = localeDirection[useLocale() as Locale] === "rtl";
  return rtl ? { back: "chevron-forward", forward: "chevron-back" } : { back: "chevron-back", forward: "chevron-forward" };
}

/** The top of a pushed screen: a back link with where it goes back to. */
export function BackBar({ label, onPress, palette }: { label: string; onPress: () => void; palette: Palette }) {
  const { back } = useBackIcon();
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={label}
      onPress={onPress}
      hitSlop={8}
      style={({ pressed }) => [local.back, { opacity: pressed ? 0.6 : 1 }]}
    >
      <Ionicons name={back} size={20} color={palette.primary} />
      <Text style={[local.backText, { color: palette.primary }]}>{label}</Text>
    </Pressable>
  );
}

/** A round avatar with the person's initials, in a soft tint of a color. */
export function Avatar({ name, color, palette, size = 40 }: { name: string; color?: string | null; palette: Palette; size?: number }) {
  const base = color ?? palette.primary;
  return (
    <View
      accessible={false}
      importantForAccessibility="no-hide-descendants"
      style={[
        local.avatar,
        { width: size, height: size, borderRadius: size / 2, backgroundColor: tint(base, 0.14), borderColor: tint(base, 0.3) },
      ]}
    >
      <Text style={{ color: palette.foreground, fontWeight: "700", fontSize: size * 0.36 }}>{initials(name)}</Text>
    </View>
  );
}

type Tone = "success" | "danger" | "muted" | "primary";

/** A small status label (checked in, no-show, a lead's stage…). */
export function Badge({ label, tone = "muted", palette }: { label: string; tone?: Tone; palette: Palette }) {
  const color = tone === "muted" ? palette.muted : palette[tone];
  return (
    <View style={[local.badge, { borderColor: tint(color, 0.45) }]}>
      <Text style={[local.badgeText, { color }]}>{label}</Text>
    </View>
  );
}

type RowProps = {
  title: string;
  subtitle?: string | null;
  /** Shown at the end of the row: a time, a price, a badge. */
  trailing?: React.ReactNode;
  /** Shown at the start: an avatar, a time, a color bar. */
  leading?: React.ReactNode;
  onPress?: () => void;
  accessibilityLabel?: string;
  palette: Palette;
};

/** One line of a list on a card surface; pressable when it opens something. */
export function ListRow({ title, subtitle, trailing, leading, onPress, accessibilityLabel, palette }: RowProps) {
  const { forward } = useBackIcon();
  const content = (
    <View style={local.row}>
      {leading}
      <View style={local.rowText}>
        <Text style={[local.rowTitle, { color: palette.foreground }]} numberOfLines={1}>
          {title}
        </Text>
        {subtitle ? (
          <Text style={[local.rowSub, { color: palette.muted }]} numberOfLines={2}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      {trailing}
      {onPress && <Ionicons name={forward} size={18} color={palette.muted} />}
    </View>
  );
  if (!onPress) return <View style={[local.rowBox, { backgroundColor: palette.surface, borderColor: palette.border }]}>{content}</View>;
  return (
    <PressableScale
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? [title, subtitle].filter(Boolean).join(", ")}
      onPress={onPress}
      style={[local.rowBox, { backgroundColor: palette.surface, borderColor: palette.border }]}
    >
      {content}
    </PressableScale>
  );
}

/** A section title with an optional action at the end ("add", "see all"). */
export function SectionTitle({
  title,
  action,
  onAction,
  palette,
}: {
  title: string;
  action?: string;
  onAction?: () => void;
  palette: Palette;
}) {
  return (
    <View style={local.section}>
      <Text role="heading" aria-level={2} style={[local.sectionTitle, { color: palette.foreground }]}>
        {title}
      </Text>
      {action && onAction && (
        <Pressable accessibilityRole="button" onPress={onAction} hitSlop={8}>
          <Text style={[local.sectionAction, { color: palette.primary }]}>{action}</Text>
        </Pressable>
      )}
    </View>
  );
}

/** A horizontal row of pills, one of them chosen (days, stages, filters). */
export function PillRow<T extends string>({
  options,
  value,
  onChange,
  label,
  palette,
}: {
  options: { value: T; label: string; sublabel?: string; accessibilityLabel?: string }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  palette: Palette;
}) {
  return (
    <ScrollView
      horizontal
      role="tablist"
      aria-label={label}
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={local.pills}
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            role="tab"
            aria-selected={selected}
            accessibilityLabel={option.accessibilityLabel ?? option.label}
            onPress={() => onChange(option.value)}
            style={[
              local.pill,
              { borderColor: selected ? palette.primary : palette.border, backgroundColor: selected ? palette.primary : palette.surface },
            ]}
          >
            {option.sublabel ? (
              <Text style={[local.pillSub, { color: selected ? palette.onPrimary : palette.muted }]}>{option.sublabel}</Text>
            ) : null}
            <Text style={[local.pillText, { color: selected ? palette.onPrimary : palette.foreground }]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

/** A number with its label, in a grid of tiles (two per row on a phone). */
export function StatTile({ label, value, palette }: { label: string; value: string; palette: Palette }) {
  return (
    <View
      accessible
      accessibilityLabel={`${label}: ${value}`}
      style={[local.stat, { backgroundColor: palette.surface, borderColor: palette.border }]}
    >
      <Text style={[local.statLabel, { color: palette.muted }]}>{label}</Text>
      <Text style={[local.statValue, { color: palette.foreground }]}>{value}</Text>
    </View>
  );
}

/** Lays tiles out two per row, wrapping. */
export function TileGrid({ children }: { children: React.ReactNode }) {
  return <View style={local.grid}>{children}</View>;
}

const local = StyleSheet.create({
  back: { flexDirection: "row", alignItems: "center", gap: 4, alignSelf: "flex-start", minHeight: 44 },
  backText: { fontSize: 16, fontWeight: "600" },
  avatar: { alignItems: "center", justifyContent: "center", borderWidth: 1 },
  badge: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 3, alignSelf: "flex-start" },
  badgeText: { fontSize: 12, fontWeight: "700" },
  rowBox: { borderWidth: 1, borderRadius: 16, paddingHorizontal: 14, paddingVertical: 12 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, minHeight: 32 },
  rowText: { flex: 1, gap: 2 },
  rowTitle: { fontSize: 16, fontWeight: "600", textAlign: "left" },
  rowSub: { fontSize: 13, textAlign: "left" },
  section: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  sectionTitle: { fontSize: 18, fontWeight: "700", textAlign: "left" },
  sectionAction: { fontSize: 15, fontWeight: "600" },
  pills: { gap: 8, paddingVertical: 2 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  stat: { flexGrow: 1, flexBasis: "45%", borderWidth: 1, borderRadius: 16, padding: 14, gap: 4 },
  statLabel: { fontSize: 13, fontWeight: "600", textAlign: "left" },
  statValue: { fontSize: 24, fontWeight: "700", textAlign: "left", fontVariant: ["tabular-nums"] },
  pill: { minWidth: 56, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 14, borderWidth: 1, alignItems: "center", gap: 2 },
  pillSub: { fontSize: 12, fontWeight: "600" },
  pillText: { fontSize: 16, fontWeight: "700" },
});
