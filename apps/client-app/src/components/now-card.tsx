import type { components } from "@business-os/api-client";
import { formatTime } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { StyleSheet, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Text } from "@business-os/app-kit/components/text";
import { Button } from "@business-os/app-kit/components/ui";
import { tint } from "@business-os/app-kit/lib/brand";
import { radius } from "@business-os/app-kit/lib/theme";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { font } from "@business-os/app-kit/lib/typography";

type Session = components["schemas"]["ScheduledSession"];

/**
 * The first thing a studio owner wants at the start of a class: what is on right now (or next), who
 * teaches it, how full it is, and one tap to take attendance.
 */
export function NowCard({
  session,
  live,
  nowMs,
  timeZone,
  palette,
}: {
  session: Session;
  live: boolean;
  nowMs: number;
  timeZone: string;
  palette: Palette;
}) {
  const t = useTranslations("business.today.nowCard");
  const locale = useLocale();
  const minutes = Math.max(1, Math.round((Date.parse(session.starts_at) - nowMs) / 60_000));
  const headline = live ? t("live") : minutes < 60 ? t("nextIn", { minutes }) : t("next");
  const where = [session.room_name ?? session.location_name].filter(Boolean).join(" · ");
  const teacher = session.instructors?.[0]?.full_name ?? session.instructor_email;
  const range = `${formatTime(session.starts_at, locale, timeZone)}-${formatTime(session.ends_at, locale, timeZone)}`;
  const isClass = session.booking_mode === "class";
  const details = [range, teacher, where].filter(Boolean).join(" · ");
  const accent = live ? palette.primary : palette.muted;
  return (
    <View
      accessible={false}
      style={[local.card, { backgroundColor: tint(palette.primary, live ? 0.1 : 0.05), borderColor: tint(palette.primary, live ? 0.45 : 0.2) }]}
    >
      <Text style={[local.kicker, { color: accent }]}>{headline}</Text>
      <Text accessibilityRole="header" style={[local.title, { color: palette.foreground }]}>
        {session.service.name}
      </Text>
      <Text style={[local.meta, { color: palette.muted }]}>{details}</Text>
      {isClass ? <Text style={[local.meta, { color: palette.foreground }]}>{t("filled", { booked: session.booked, capacity: session.capacity })}</Text> : null}
      <Button
        label={isClass ? t("attendance") : t("open")}
        accessibilityLabel={`${isClass ? t("attendance") : t("open")}: ${session.service.name}`}
        palette={palette}
        onPress={() => router.push(`/session/${session.id}`)}
      />
    </View>
  );
}

const local = StyleSheet.create({
  card: { borderWidth: 1, borderRadius: radius.card, padding: 16, gap: 6 },
  kicker: { fontSize: 13, ...font.semibold, textTransform: "uppercase", textAlign: "left" },
  title: { fontSize: 20, ...font.semibold, textAlign: "left" },
  meta: { fontSize: 15, ...font.regular, textAlign: "left" },
});
