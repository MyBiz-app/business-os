import { dayOf, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { SessionCard } from "@/components/session-card";
import { Button, Card, elevation, Heading, Screen, styles } from "@/components/ui";
import { assetUrl, unwrap } from "@/lib/api";
import { tint } from "@/lib/brand";
import { useHealth } from "@/lib/use-health";
import { useLoad } from "@/lib/use-load";
import { verticalOf } from "@/lib/vertical";
import { useBusiness } from "@/providers/business-provider";

/** Branded home: the business, the client's next booking and what's on today. */
export default function Home() {
  const t = useTranslations("client.home");
  const tHealth = useTranslations("client.health");
  const tTerms = useTranslations("terms");
  const tAppointment = useTranslations("client.appointment");
  const health = useHealth();
  const locale = useLocale();
  const formatDay = (day: string) =>
    new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: "UTC" }).format(new Date(`${day}T12:00:00Z`));
  const { api, scope, business, palette } = useBusiness();

  const load = useCallback(async () => {
    if (!business) return { sessions: [], appointments: 0 };
    const start = todayIn(business.time_zone);
    const [sessions, services] = await Promise.all([
      api.GET("/client/sessions", { params: { ...scope, query: { start, days: 14 } } }),
      api.GET("/client/appointments/services", { params: scope }),
    ]);
    return { sessions: unwrap(sessions), appointments: services.data?.length ?? 0 };
  }, [api, scope, business]);
  const { data, loading, reload } = useLoad(load);
  const sessions = data?.sessions;

  if (!business) return null;
  const today = todayIn(business.time_zone);
  const next = sessions?.find((s) => s.my_booking && s.status === "scheduled");
  const todays = (sessions ?? []).filter(
    (s) => dayOf(s.starts_at, business.time_zone) === today && s.status === "scheduled" && s.id !== next?.id,
  );
  const logo = assetUrl(business.logo_url);
  const update = () => void reload();

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <View style={[local.hero, elevation.raised, { backgroundColor: palette.primary }]}>
        {/* Soft light circles give the brand color depth. */}
        <View aria-hidden style={[local.orb, local.orbLarge, { backgroundColor: tint(palette.onPrimary === "#ffffff" ? "#ffffff" : "#000000", 0.12) }]} />
        <View aria-hidden style={[local.orb, local.orbSmall, { backgroundColor: tint(palette.onPrimary === "#ffffff" ? "#ffffff" : "#000000", 0.08) }]} />
        {logo && <Image source={{ uri: logo }} style={local.logo} accessibilityIgnoresInvertColors />}
        <Text accessibilityRole="header" style={[local.business, { color: palette.onPrimary }]}>
          {business.name}
        </Text>
        <Text style={[local.greeting, { color: palette.onPrimary }]}>
          {t("greeting", { name: business.first_name })}
        </Text>
      </View>

      {health?.required && health.state !== "ok" && (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.foreground }]}>
            {health.state === "needs_review" || health.state === "rejected"
              ? tHealth("reviewPending")
              : health.state === "expiring" && health.current
                ? tHealth("expiringBanner", { date: formatDay(health.current.valid_until) })
                : tHealth("banner")}
          </Text>
          {health.state !== "needs_review" && health.state !== "rejected" && (
            <Button
              label={health.state === "expiring" ? tHealth("update") : tHealth("fill")}
              palette={palette}
              onPress={() => router.push("/health")}
            />
          )}
        </Card>
      )}

      <Heading palette={palette} level={2}>
        {tTerms(`${verticalOf(business)}.nextBooking`)}
      </Heading>
      {next ? (
        <SessionCard session={next} onChange={update} showDay />
      ) : (
        <Text style={[styles.muted, { color: palette.muted }]}>{loading ? "…" : t("noUpcoming")}</Text>
      )}

      {todays.length > 0 && (
        <>
          <Heading palette={palette} level={2}>
            {t("today")}
          </Heading>
          {todays.map((session) => (
            <SessionCard key={session.id} session={session} onChange={update} />
          ))}
        </>
      )}

      {(data?.appointments ?? 0) > 0 ? (
        <>
          <Button label={tAppointment("cta")} palette={palette} onPress={() => router.push("/appointment")} />
          <Button
            label={tTerms(`${verticalOf(business)}.appTab`)}
            palette={palette}
            variant="secondary"
            onPress={() => router.navigate("/schedule")}
          />
        </>
      ) : (
        <Button label={t("bookClass")} palette={palette} onPress={() => router.navigate("/schedule")} />
      )}
    </Screen>
  );
}

const local = StyleSheet.create({
  hero: { borderRadius: 24, padding: 22, paddingVertical: 28, gap: 6, overflow: "hidden" },
  orb: { position: "absolute", borderRadius: 999 },
  orbLarge: { width: 220, height: 220, top: -90, end: -60 },
  orbSmall: { width: 120, height: 120, bottom: -50, end: 70 },
  logo: { width: 48, height: 48, borderRadius: 12, backgroundColor: "#ffffff" },
  business: { fontSize: 26, fontWeight: "700", textAlign: "left" },
  greeting: { fontSize: 16, textAlign: "left" },
});
