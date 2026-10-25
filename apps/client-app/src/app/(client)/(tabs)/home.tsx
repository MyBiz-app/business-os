import { router, useFocusEffect } from "expo-router";
import { Fragment, useEffect } from "react";
import { Image, Linking, StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { fixedColors, radius } from "@business-os/app-kit/lib/theme";
import { useLocale, useTranslations } from "use-intl";

import { BusinessStrip } from "@/components/business-strip";
import { HOME_CARDS, type HomeData } from "@/components/home-cards";
import { Badge, ListRow } from "@business-os/app-kit/components/rows";
import { ListSkeleton } from "@business-os/app-kit/components/skeleton";
import { Button, Card, LoadError, Screen, styles } from "@business-os/app-kit/components/ui";
import { assetUrl } from "@business-os/app-kit/lib/api";
import { WEB_URL } from "@business-os/app-kit/lib/env";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { tint } from "@business-os/app-kit/lib/brand";
import { colors } from "@business-os/app-kit/lib/theme";
import { useHealth } from "@/lib/use-health";
import { useCachedLoad } from "@business-os/app-kit/lib/use-cached-load";
import { homeKey, loadHome, prefetchTabs } from "@/lib/client-data";
import { useDataContext } from "@/lib/use-data-context";
import { homeCardsOnHome, pickAction } from "@business-os/app-kit/lib/client-home";
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
  const tReview = useTranslations("client.review");
  const health = useHealth();
  const locale = useLocale();
  const formatDay = (day: string) =>
    new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: "UTC" }).format(new Date(`${day}T12:00:00Z`));
  const { business, businesses, palette } = useBusiness();
  const account = useAccount();
  const overview = useOverview();
  const openBusiness = useOpenBusiness();
  const multi = (businesses?.length ?? 0) > 1;
  const swipe = useBusinessSwipe(
    (businesses ?? []).map((b) => b.id),
    business?.id ?? null,
    (id) => void openBusiness(id),
  );

  const ctx = useDataContext();
  const { data, error, refreshing, reload, revalidate } = useCachedLoad(
    ctx ? homeKey(ctx) : ["home"],
    () => (ctx ? loadHome(ctx) : Promise.resolve(null)),
    { enabled: Boolean(ctx) },
  );
  // Once home is on screen, the other tabs are fetched quietly so moving to them needs no waiting.
  useEffect(() => {
    if (ctx && data) prefetchTabs(ctx);
  }, [ctx, data]);
  const locations = useLocations();
  // Coming back (e.g. after rating a visit) shows fresh data.
  useFocusEffect(revalidate);

  if (!business) return null;
  const homeCards = homeCardsOnHome(homeCardsFor(business));
  const homeData = (loaded: NonNullable<typeof data>): HomeData => ({ ...loaded, locations, reload: () => void reload() });
  const logo = assetUrl(business.logo_url);

  const toReview = data?.toReview[0];
  const waiting = pickAction({
    health: Boolean(health?.required && health.state !== "ok" && health.state !== "needs_review" && health.state !== "rejected"),
    pay: account.toPay.length,
    answer: account.toAnswer.length,
    sign: account.toSign.length,
    review: toReview ? 1 : 0,
  });
  const healthText =
    health?.state === "expiring" && health.current ? tHealth("expiringBanner", { date: formatDay(health.current.valid_until) }) : tHealth("banner");
  const pay = account.toPay[0];
  const answer = account.toAnswer[0];
  const sign = account.toSign[0];
  const needsYou = waiting.first && (
    <Card palette={palette}>
      <Text accessibilityRole="header" style={[local.reviewTitle, { color: palette.foreground }]}>
        {t("needsYou")}
      </Text>
      {waiting.first === "health" && (
        <>
          <Text style={[styles.muted, { color: palette.foreground }]}>{healthText}</Text>
          <Button label={health?.state === "expiring" ? tHealth("update") : tHealth("fill")} palette={palette} onPress={() => router.push("/health")} />
        </>
      )}
      {waiting.first === "pay" && pay && (
        <ListRow
          palette={palette}
          title={t(pay.kind === "bill" ? "payBill" : "payDeposit", { number: pay.number })}
          subtitle={pay.title}
          trailing={<Badge label={formatMoney(pay.deposit_due, pay.currency, locale)} tone="primary" palette={palette} />}
          onPress={() => void Linking.openURL(`${WEB_URL}/q/${pay.token}`)}
        />
      )}
      {waiting.first === "answer" && answer && (
        <ListRow
          palette={palette}
          title={t("answerQuote", { number: answer.number })}
          subtitle={`${answer.title} · ${formatMoney(answer.total, answer.currency, locale)}`}
          onPress={() => void Linking.openURL(`${WEB_URL}/q/${answer.token}`)}
        />
      )}
      {waiting.first === "sign" && sign && (
        <ListRow palette={palette} title={t("signDocument", { name: sign.name })} subtitle={t("signHint")} onPress={() => router.push("/documents")} />
      )}
      {waiting.first === "review" && toReview && (
        <>
          <Text style={[local.reviewTitle, { color: palette.foreground }]}>{tReview("cardTitle", { service: toReview.service_name })}</Text>
          <Text style={[styles.muted, { color: palette.muted }]}>{tReview("cardText")}</Text>
          <Button
            label={tReview("rate")}
            palette={palette}
            variant="secondary"
            onPress={() => router.push({ pathname: "/review/[id]", params: { id: toReview.booking_id, service: toReview.service_name } })}
          />
        </>
      )}
      {waiting.others > 0 && (
        <ListRow palette={palette} title={t("moreWaiting", { count: waiting.others })} onPress={() => router.navigate("/bookings")} />
      )}
    </Card>
  );

  const screen = (
    <Screen
      palette={palette}
      refreshing={refreshing}
      onRefresh={() => void reload()}
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

      {error !== undefined && !data && <LoadError palette={palette} onRetry={() => void reload()} />}
      {error === undefined && !data && <ListSkeleton palette={palette} />}

      {homeCards.map((card) => {
        const Card = HOME_CARDS[card];
        return data ? (
          <Fragment key={card}>
            <Card data={homeData(data)} />
            {/* Right under the next booking: the one thing that needs the client, if anything. */}
            {card === (homeCards.includes("next_booking") ? "next_booking" : homeCards[0]) && needsYou}
          </Fragment>
        ) : null;
      })}
      {data && homeCards.length === 0 && needsYou}
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
  hero: { borderRadius: radius.dialog, padding: 20, gap: 4, overflow: "hidden" },
  orb: { position: "absolute", borderRadius: radius.pill },
  orbLarge: { width: 220, height: 220, top: -90, end: -60 },
  orbSmall: { width: 120, height: 120, bottom: -50, end: 70 },
  logo: { width: 48, height: 48, borderRadius: radius.card, backgroundColor: colors.light.surface },
  business: { fontSize: 24, fontWeight: "600", textAlign: "left" },
  greeting: { fontSize: 15, textAlign: "left" },
  reviewTitle: { fontSize: 17, fontWeight: "600", textAlign: "left" },
});
