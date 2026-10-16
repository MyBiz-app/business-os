import type { components } from "@business-os/api-client";
import { formatTime, todayIn } from "@business-os/i18n/dates";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Badge, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, EmptyState, Heading, LoadError, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { tint } from "@business-os/app-kit/lib/brand";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { BookingActions } from "@/components/booking-actions";
import { addressOf, useLocations } from "@/lib/use-locations";
import { useBusiness } from "@/providers/business-provider";

type Booking = components["schemas"]["ClientBooking"];
type Entitlement = components["schemas"]["Entitlement"];
type Plan = components["schemas"]["Plan"];

const TONE: Partial<Record<Booking["status"], "primary" | "success" | "danger" | "muted">> = {
  booked: "primary",
  checked_in: "success",
  no_show: "danger",
};
/** History shows the latest visits first; the rest on request. */
const HISTORY_PAGE = 10;

const CURRENT = new Set<Entitlement["state"]>(["active", "upcoming", "frozen"]);

/** The client's plans, upcoming bookings (soonest first) and history. */
export default function Bookings() {
  const t = useTranslations("client.bookings");
  const tStatus = useTranslations("bookings");
  const tPlans = useTranslations("plans");
  const tReceipts = useTranslations("receipts");
  const tReview = useTranslations("client.review");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();

  const load = useCallback(async () => {
    if (!business) return null;
    const [all, entitlements, plans, sessions] = await Promise.all([
      api.GET("/client/bookings", { params: scope }).then(unwrap),
      api.GET("/client/entitlements", { params: scope }).then(unwrap),
      api.GET("/client/plans", { params: scope }).then(unwrap),
      // Only to learn where each upcoming booking takes place (navigation).
      api.GET("/client/sessions", { params: { ...scope, query: { start: todayIn(business.time_zone), days: 14 } } }).then((r) => r.data ?? []),
    ]);
    const now = Date.now();
    return {
      upcoming: all.filter((b) => Date.parse(b.starts_at) >= now && b.status !== "cancelled").reverse(),
      past: all.filter((b) => Date.parse(b.starts_at) < now || b.status === "cancelled"),
      current: entitlements.filter((e) => CURRENT.has(e.state)),
      plans,
      branchOf: new Map(sessions.map((x) => [x.id, x.location_name])),
    };
  }, [api, scope, business]);
  const { data, error, loading, reload } = useLoad(load);
  const locations = useLocations();
  const [buying, setBuying] = useState<string | null>(null);
  const [allHistory, setAllHistory] = useState(false);
  const [purchase, setPurchase] = useState<{ ok: boolean; message: string } | null>(null);

  // Coming back from the payment page shows the new plan.
  useFocusEffect(
    useCallback(() => {
      void reload();
    }, [reload]),
  );

  /** Starts a checkout at the plan's current price and opens the payment page. */
  const buy = async (plan: Plan) => {
    if (!business) return;
    setBuying(plan.id);
    setPurchase(null);
    try {
      const checkout = unwrap(await api.POST("/client/checkouts", { params: scope, body: { plan_id: plan.id } }));
      router.push(`/pay/${checkout.id}`);
    } catch {
      setPurchase({ ok: false, message: t("buyFailed") });
    } finally {
      setBuying(null);
    }
  };

  if (!business) return null;
  const date = new Intl.DateTimeFormat(locale, {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: business.time_zone,
  });
  const day = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone: "UTC" });
  const money = (amount: number, currency: string) => formatMoney(amount, currency, locale);

  const row = (booking: Booking) => (
    <View key={booking.id} style={local.row}>
      <View style={local.info}>
        <Text style={[local.name, { color: palette.foreground }]}>{booking.service_name}</Text>
        <Text style={[local.meta, { color: palette.muted }]}>
          {date.format(new Date(booking.starts_at))} · {formatTime(booking.starts_at, locale, business.time_zone)}
        </Text>
        {booking.rating ? (
          <Text style={[local.meta, { color: palette.muted }]}>{tReview("rated", { count: booking.rating })}</Text>
        ) : null}
      </View>
      <Badge
        label={
          (booking.session_status === "cancelled" ? tStatus("sessionCancelled") : tStatus(`statuses.${booking.status}`)) +
          (booking.late_cancel ? ` · ${tStatus("lateCancel")}` : "")
        }
        tone={TONE[booking.session_status === "cancelled" ? "cancelled" : booking.status] ?? "muted"}
        palette={palette}
      />
    </View>
  );

  const dayNumber = new Intl.DateTimeFormat(locale, { day: "numeric", timeZone: business.time_zone });
  const monthShort = new Intl.DateTimeFormat(locale, { month: "short", timeZone: business.time_zone });
  /** An upcoming booking: its date, time and status, with navigate / calendar / cancel. */
  const upcomingCard = (booking: Booking) => (
    <View key={booking.id} style={[local.upcoming, { borderColor: palette.border }]}>
      <View style={local.upcomingHead}>
        <View style={[local.dateBlock, { backgroundColor: tint(palette.primary, 0.12) }]}>
          <Text style={[local.dateDay, { color: palette.primary }]}>{dayNumber.format(new Date(booking.starts_at))}</Text>
          <Text style={[local.dateMonth, { color: palette.primary }]}>{monthShort.format(new Date(booking.starts_at))}</Text>
        </View>
        <View style={local.info}>
          <Text style={[local.name, { color: palette.foreground }]}>{booking.service_name}</Text>
          <Text style={[local.meta, { color: palette.muted }]}>
            {formatTime(booking.starts_at, locale, business.time_zone)}-{formatTime(booking.ends_at, locale, business.time_zone)}
            {booking.dependent_name ? ` · ${booking.dependent_name}` : ""}
          </Text>
        </View>
        <Badge label={tStatus(`statuses.${booking.status}`)} tone={TONE[booking.status] ?? "muted"} palette={palette} />
      </View>
      <BookingActions
        booking={booking}
        address={addressOf(locations, data?.branchOf.get(booking.session_id))}
        onChange={() => void reload()}
        only={booking.status === "waitlisted" ? "cancel" : undefined}
      />
    </View>
  );

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <Heading palette={palette}>{t("title")}</Heading>
      {error !== undefined && !data && <LoadError palette={palette} onRetry={() => void reload()} />}

      <Heading palette={palette} level={2}>
        {t("myPlans")}
      </Heading>
      {data?.current.length ? (
        <Card palette={palette}>
          {data.current.map((entitlement) => (
            <View key={entitlement.id} style={local.row}>
              <View style={local.info}>
                <Text style={[local.name, { color: palette.foreground }]}>{entitlement.name}</Text>
                <Text style={[local.meta, { color: palette.muted }]}>
                  {t("validUntil", { date: day.format(new Date(`${entitlement.ends_on}T12:00:00Z`)) })}
                </Text>
              </View>
              {entitlement.receipt_id && (
                <Text
                  accessibilityRole="link"
                  onPress={() => router.push(`/receipt/${entitlement.receipt_id}`)}
                  style={[local.meta, { color: palette.primary, textDecorationLine: "underline" }]}
                >
                  {tReceipts("short", { number: entitlement.receipt_number ?? "" })}
                </Text>
              )}
              <Text style={[local.status, { color: palette.primary }]}>
                {entitlement.state !== "active"
                  ? tPlans(`states.${entitlement.state}`)
                  : entitlement.credits_remaining === null
                    ? tPlans("kinds.membership")
                    : t("entriesLeft", { count: entitlement.credits_remaining })}
              </Text>
            </View>
          ))}
        </Card>
      ) : data && !business.online_sales ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.foreground }]}>{t("noPlan")}</Text>
          {data.plans.map((plan) => (
            <View key={plan.id} style={local.row}>
              <Text style={[local.meta, local.info, { color: palette.foreground }]}>{plan.name}</Text>
              <Text style={[local.meta, { color: palette.muted }]}>{money(plan.price_amount, plan.price_currency)}</Text>
            </View>
          ))}
        </Card>
      ) : null}

      {data && business.online_sales && data.plans.length > 0 && (
        <>
          <Heading palette={palette} level={2}>
            {t("buyTitle")}
          </Heading>
          <Card palette={palette}>
            {data.current.length === 0 && (
              <Text style={[styles.muted, { color: palette.foreground }]}>{t("noPlanBuy")}</Text>
            )}
            {data.plans.map((plan) => (
              <View key={plan.id} style={local.row}>
                <View style={local.info}>
                  <Text style={[local.name, { color: palette.foreground }]}>{plan.name}</Text>
                  <Text style={[local.meta, { color: palette.muted }]}>
                    {money(plan.price_amount, plan.price_currency)}
                  </Text>
                </View>
                <View style={local.buy}>
                  <Button
                    label={t("buy")}
                    accessibilityLabel={`${t("buy")} - ${plan.name}`}
                    palette={palette}
                    busy={buying === plan.id}
                    disabled={buying !== null}
                    onPress={() => void buy(plan)}
                  />
                </View>
              </View>
            ))}
            {purchase && (
              <Text
                accessibilityRole={purchase.ok ? undefined : "alert"}
                accessibilityLiveRegion="polite"
                style={[local.meta, { color: purchase.ok ? palette.primary : palette.danger }]}
              >
                {purchase.message}
              </Text>
            )}
          </Card>
        </>
      )}

      <Heading palette={palette} level={2}>
        {t("upcoming")}
      </Heading>
      {data?.upcoming.length ? (
        <View style={local.upcomingList}>{data.upcoming.map(upcomingCard)}</View>
      ) : error !== undefined && !data ? null : (
        <EmptyState palette={palette} message={t("noUpcoming")} loading={loading} />
      )}
      {data?.past.length ? (
        <>
          <SectionTitle
            title={t("history")}
            action={!allHistory && data.past.length > HISTORY_PAGE ? t("showAll", { count: data.past.length }) : undefined}
            onAction={() => setAllHistory(true)}
            palette={palette}
          />
          <Card palette={palette}>{(allHistory ? data.past : data.past.slice(0, HISTORY_PAGE)).map(row)}</Card>
        </>
      ) : null}
      <ListRow palette={palette} title={t("receipts")} onPress={() => router.push("/receipts")} />
    </Screen>
  );
}

const local = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 8 },
  info: { flex: 1, gap: 2 },
  name: { fontSize: 16, fontWeight: "600", textAlign: "left" },
  meta: { fontSize: 14, textAlign: "left" },
  status: { fontSize: 14, fontWeight: "600" },
  buy: { minWidth: 96 },
  upcomingList: { gap: 12 },
  upcoming: { borderWidth: 1, borderRadius: 20, padding: 14, gap: 12 },
  upcomingHead: { flexDirection: "row", alignItems: "center", gap: 12 },
  dateBlock: { width: 54, paddingVertical: 8, borderRadius: 14, alignItems: "center" },
  dateDay: { fontSize: 20, fontWeight: "800" },
  dateMonth: { fontSize: 12, fontWeight: "600", textTransform: "uppercase" },
});
