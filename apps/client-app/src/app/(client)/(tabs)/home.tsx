import { todayIn } from "@business-os/i18n/dates";
import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { Image, Linking, StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { fixedColors, radius } from "@business-os/app-kit/lib/theme";
import { useLocale, useTranslations } from "use-intl";

import { BusinessStrip } from "@/components/business-strip";
import { HOME_CARDS, type HomeData } from "@/components/home-cards";
import { Badge, ListRow } from "@business-os/app-kit/components/rows";
import { Button, Card, LoadError, Screen, styles } from "@business-os/app-kit/components/ui";
import { assetUrl, unwrap } from "@business-os/app-kit/lib/api";
import { WEB_URL } from "@business-os/app-kit/lib/env";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { tint } from "@business-os/app-kit/lib/brand";
import { colors } from "@business-os/app-kit/lib/theme";
import { useHealth } from "@/lib/use-health";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { homeCardsFor } from "@business-os/app-kit/lib/vertical";
import { useAccount } from "@/lib/use-account";
import { useBusinessSwipe } from "@/lib/use-business-swipe";
import { useLocations } from "@/lib/use-locations";
import { useOpenBusiness } from "@/lib/use-open-business";
import { useOverview } from "@/lib/use-overview";
import { useBusiness } from "@/providers/business-provider";

/** Branded home: what needs attention, then the cards the business's industry lists (its
 * `client_home` in the industry catalog). */
export default function Home() {
  const t = useTranslations("client.home");
  const tHealth = useTranslations("client.health");
  const tAppointment = useTranslations("client.appointment");
  const tReview = useTranslations("client.review");
  const health = useHealth();
  const locale = useLocale();
  const formatDay = (day: string) =>
    new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: "UTC" }).format(new Date(`${day}T12:00:00Z`));
  const { api, scope, business, businesses, palette } = useBusiness();
  const account = useAccount();
  const overview = useOverview();
  const openBusiness = useOpenBusiness();
  const multi = (businesses?.length ?? 0) > 1;
  const swipe = useBusinessSwipe(
    (businesses ?? []).map((b) => b.id),
    business?.id ?? null,
    (id) => void openBusiness(id),
  );

  const load = useCallback(async () => {
    if (!business) return null;
    const start = todayIn(business.time_zone);
    const [bookings, sessions, entitlements, services, pending, courts] = await Promise.all([
      api.GET("/client/bookings", { params: scope }),
      api.GET("/client/sessions", { params: { ...scope, query: { start, days: 14 } } }),
      api.GET("/client/entitlements", { params: scope }),
      api.GET("/client/appointments/services", { params: scope }),
      api.GET("/client/reviews/pending", { params: scope }),
      api.GET("/client/resources", { params: scope }),
    ]);
    return {
      bookings: unwrap(bookings),
      sessions: unwrap(sessions),
      entitlements: entitlements.data ?? [],
      appointments: services.data?.length ?? 0,
      courts: courts.data?.length ?? 0,
      toReview: pending.data ?? [],
    };
  }, [api, scope, business]);
  const { data, error, loading, reload } = useLoad(load);
  const locations = useLocations();
  // Coming back (e.g. after rating a visit) shows fresh data.
  useFocusEffect(
    useCallback(() => {
      void reload();
    }, [reload]),
  );

  if (!business) return null;
  const homeCards = homeCardsFor(business);
  const homeData = (loaded: NonNullable<typeof data>): HomeData => ({ ...loaded, locations, reload: () => void reload() });
  const logo = assetUrl(business.logo_url);

  const screen = (
    <Screen
      palette={palette}
      refreshing={loading}
      onRefresh={() => void reload()}
      footer={
        (data?.appointments ?? 0) > 0 ? (
          <Button label={tAppointment("cta")} palette={palette} onPress={() => router.push("/appointment")} />
        ) : (
          <Button label={t("bookClass")} palette={palette} onPress={() => router.navigate("/schedule")} />
        )
      }
    >
      {multi && <BusinessStrip palette={palette} overview={overview.data} />}

      <View style={[local.hero, { backgroundColor: palette.primary }]}>
        {/* Soft light circles give the brand color depth. */}
        <View aria-hidden style={[local.orb, local.orbLarge, { backgroundColor: tint(palette.onPrimary, 0.12) }]} />
        <View aria-hidden style={[local.orb, local.orbSmall, { backgroundColor: tint(palette.onPrimary, 0.08) }]} />
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

      {account.toPay.length + account.toAnswer.length + account.toSign.length > 0 && (
        <Card palette={palette}>
          <Text accessibilityRole="header" style={[local.reviewTitle, { color: palette.foreground }]}>
            {t("waiting")}
          </Text>
          {account.toPay.map((quote) => (
            <ListRow
              key={`pay-${quote.token}`}
              palette={palette}
              title={t(quote.kind === "bill" ? "payBill" : "payDeposit", { number: quote.number })}
              subtitle={quote.title}
              trailing={<Badge label={formatMoney(quote.deposit_due, quote.currency, locale)} tone="primary" palette={palette} />}
              onPress={() => void Linking.openURL(`${WEB_URL}/q/${quote.token}`)}
            />
          ))}
          {account.toAnswer.map((quote) => (
            <ListRow
              key={`answer-${quote.token}`}
              palette={palette}
              title={t("answerQuote", { number: quote.number })}
              subtitle={`${quote.title} · ${formatMoney(quote.total, quote.currency, locale)}`}
              onPress={() => void Linking.openURL(`${WEB_URL}/q/${quote.token}`)}
            />
          ))}
          {account.toSign.map((document) => (
            <ListRow
              key={`sign-${document.id}`}
              palette={palette}
              title={t("signDocument", { name: document.name })}
              subtitle={t("signHint")}
              onPress={() => router.push("/documents")}
            />
          ))}
        </Card>
      )}

      {data?.toReview[0] && (
        <Card palette={palette}>
          <Text style={[local.reviewTitle, { color: palette.foreground }]}>
            {tReview("cardTitle", { service: data.toReview[0].service_name })}
          </Text>
          <Text style={[styles.muted, { color: palette.muted }]}>{tReview("cardText")}</Text>
          <Button
            label={tReview("rate")}
            palette={palette}
            variant="secondary"
            onPress={() =>
              router.push({
                pathname: "/review/[id]",
                params: { id: data.toReview[0].booking_id, service: data.toReview[0].service_name },
              })
            }
          />
        </Card>
      )}

      {error !== undefined && !data && <LoadError palette={palette} onRetry={() => void reload()} />}

      {homeCards.map((card) => {
        const Card = HOME_CARDS[card];
        return data ? <Card key={card} data={homeData(data)} /> : null;
      })}
    </Screen>
  );
  // Swiping sideways over the home screen moves to the next business (only with two or more).
  return multi ? (
    <View style={local.fill} {...swipe}>
      {screen}
    </View>
  ) : (
    screen
  );
}

const local = StyleSheet.create({
  fill: { flex: 1 },
  hero: { borderRadius: radius.dialog, padding: 24, paddingVertical: 32, gap: 6, overflow: "hidden" },
  orb: { position: "absolute", borderRadius: radius.pill },
  orbLarge: { width: 220, height: 220, top: -90, end: -60 },
  orbSmall: { width: 120, height: 120, bottom: -50, end: 70 },
  logo: { width: 48, height: 48, borderRadius: radius.card, backgroundColor: colors.light.surface },
  business: { fontSize: 30, fontWeight: "600", textAlign: "left" },
  greeting: { fontSize: 15, textAlign: "left" },
  reviewTitle: { fontSize: 17, fontWeight: "600", textAlign: "left" },
});
