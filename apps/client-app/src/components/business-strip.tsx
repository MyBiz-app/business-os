import Ionicons from "@expo/vector-icons/Ionicons";
import { router, usePathname } from "expo-router";
import { Image, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { Text } from "@business-os/app-kit/components/text";
import { assetUrl } from "@business-os/app-kit/lib/api";
import { circleInitials, waitingCounts } from "@business-os/app-kit/lib/all-mine";
import { tint } from "@business-os/app-kit/lib/brand";
import { font } from "@business-os/app-kit/lib/typography";
import { radius, space, type Palette } from "@business-os/app-kit/lib/theme";
import { useOpenBusiness } from "@/lib/use-open-business";
import type { ClientOverview } from "@/lib/use-overview";
import { useBusiness } from "@/providers/business-provider";

const SIZE = 56;

/** The person's businesses as circles with their logos, like stories: the first is "All mine".
 * A tap switches business at once (the whole app takes its color and logo); a dot means something
 * waits for them there. Shown only to someone with two businesses or more. */
export function BusinessStrip({ palette, overview }: { palette: Palette; overview?: ClientOverview | null }) {
  const t = useTranslations("client.all");
  const { businesses, business } = useBusiness();
  const open = useOpenBusiness();
  const onAll = usePathname() === "/all";
  if (!businesses || businesses.length < 2) return null;
  const counts = waitingCounts(overview?.waiting ?? []);
  const anyWaiting = Object.keys(counts).length > 0;

  return (
    <View accessibilityRole="tablist" accessibilityLabel={t("strip")}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={local.row}>
        <Circle
          label={t("circle")}
          selected={onAll}
          color={palette.primary}
          palette={palette}
          dot={anyWaiting}
          onPress={() => router.navigate("/all")}
          a11y={t("circle")}
        >
          <Ionicons name="apps" size={24} color={palette.primaryInk} />
        </Circle>
        {businesses.map((b) => {
          const logo = assetUrl(b.logo_url);
          const color = b.primary_color ?? palette.primary;
          return (
            <Circle
              key={b.id}
              label={b.name}
              selected={!onAll && b.id === business?.id}
              color={color}
              palette={palette}
              dot={(counts[b.id] ?? 0) > 0}
              onPress={() => void open(b.id)}
              a11y={(counts[b.id] ?? 0) > 0 ? t("circleWaiting", { name: b.name }) : b.name}
            >
              {logo ? (
                <Image source={{ uri: logo }} style={local.logo} accessibilityIgnoresInvertColors />
              ) : (
                <Text style={{ color: palette.foreground, ...font.semibold, fontSize: 17 }}>{circleInitials(b.name)}</Text>
              )}
            </Circle>
          );
        })}
      </ScrollView>
    </View>
  );
}

function Circle({
  label,
  selected,
  color,
  palette,
  dot,
  onPress,
  a11y,
  children,
}: {
  label: string;
  selected: boolean;
  color: string;
  palette: Palette;
  dot: boolean;
  onPress: () => void;
  a11y: string;
  children: React.ReactNode;
}) {
  return (
    <Pressable
      accessibilityRole="tab"
      accessibilityState={{ selected }}
      accessibilityLabel={a11y}
      onPress={onPress}
      style={local.item}
    >
      <View
        style={[
          local.ring,
          { borderColor: selected ? color : palette.border, borderWidth: selected ? 2 : 1 },
        ]}
      >
        <View style={[local.circle, { backgroundColor: tint(color, 0.14) }]}>{children}</View>
        {dot && <View style={[local.dot, { backgroundColor: palette.primary, borderColor: palette.background }]} />}
      </View>
      <Text numberOfLines={1} style={[local.label, { color: selected ? palette.foreground : palette.muted }]}>
        {label}
      </Text>
    </Pressable>
  );
}

const local = StyleSheet.create({
  row: { gap: space.md, paddingVertical: space.xs, paddingHorizontal: 2 },
  item: { width: SIZE + 16, alignItems: "center", gap: space.xs },
  ring: { width: SIZE + 8, height: SIZE + 8, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  circle: { width: SIZE, height: SIZE, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", overflow: "hidden" },
  logo: { width: SIZE, height: SIZE },
  dot: { position: "absolute", top: 0, end: 0, width: 14, height: 14, borderRadius: radius.pill, borderWidth: 2 },
  label: { fontSize: 12, ...font.medium, textAlign: "center", maxWidth: SIZE + 16 },
});
