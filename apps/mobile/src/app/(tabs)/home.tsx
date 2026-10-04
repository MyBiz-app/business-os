import { dayOf, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { useTranslations } from "use-intl";

import { SessionCard } from "@/components/session-card";
import { Button, Card, Heading, Screen, styles } from "@/components/ui";
import { assetUrl, unwrap } from "@/lib/api";
import { useHealth } from "@/lib/use-health";
import { useLoad } from "@/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

/** Branded home: the business, the client's next booking and what's on today. */
export default function Home() {
  const t = useTranslations("client.home");
  const tHealth = useTranslations("client.health");
  const health = useHealth();
  const { api, scope, business, palette } = useBusiness();

  const load = useCallback(async () => {
    if (!business) return [];
    const start = todayIn(business.time_zone);
    return unwrap(await api.GET("/client/sessions", { params: { ...scope, query: { start, days: 14 } } }));
  }, [api, scope, business]);
  const { data: sessions, loading, reload } = useLoad(load);

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
      <View style={[local.hero, { backgroundColor: palette.primary }]}>
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
              : tHealth("banner")}
          </Text>
          {health.state !== "needs_review" && health.state !== "rejected" && (
            <Button label={tHealth("fill")} palette={palette} onPress={() => router.push("/health")} />
          )}
        </Card>
      )}

      <Heading palette={palette} level={2}>
        {t("nextBooking")}
      </Heading>
      {next ? (
        <SessionCard session={next} onChange={update} />
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

      <Button label={t("bookClass")} palette={palette} onPress={() => router.navigate("/schedule")} />
    </Screen>
  );
}

const local = StyleSheet.create({
  hero: { borderRadius: 20, padding: 20, gap: 6 },
  logo: { width: 48, height: 48, borderRadius: 12, backgroundColor: "#ffffff" },
  business: { fontSize: 26, fontWeight: "700", textAlign: "left" },
  greeting: { fontSize: 16, textAlign: "left" },
});
