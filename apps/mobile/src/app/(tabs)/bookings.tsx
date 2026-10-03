import type { components } from "@business-os/api-client";
import { formatTime } from "@business-os/i18n/dates";
import { useCallback } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Card, Heading, Screen, styles } from "@/components/ui";
import { unwrap } from "@/lib/api";
import { useLoad } from "@/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Booking = components["schemas"]["ClientBooking"];
type Entitlement = components["schemas"]["Entitlement"];

const CURRENT = new Set<Entitlement["state"]>(["active", "upcoming", "frozen"]);

/** The client's plans, upcoming bookings (soonest first) and history. */
export default function Bookings() {
  const t = useTranslations("client.bookings");
  const tStatus = useTranslations("bookings");
  const tPlans = useTranslations("plans");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();

  const load = useCallback(async () => {
    if (!business) return null;
    const [all, entitlements, plans] = await Promise.all([
      api.GET("/client/bookings", { params: scope }).then(unwrap),
      api.GET("/client/entitlements", { params: scope }).then(unwrap),
      api.GET("/client/plans", { params: scope }).then(unwrap),
    ]);
    const now = Date.now();
    return {
      upcoming: all.filter((b) => Date.parse(b.starts_at) >= now && b.status !== "cancelled").reverse(),
      past: all.filter((b) => Date.parse(b.starts_at) < now || b.status === "cancelled"),
      current: entitlements.filter((e) => CURRENT.has(e.state)),
      plans,
    };
  }, [api, scope, business]);
  const { data, loading, reload } = useLoad(load);

  if (!business) return null;
  const date = new Intl.DateTimeFormat(locale, {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: business.time_zone,
  });
  const day = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone: "UTC" });
  const money = (amount: number, currency: string) =>
    new Intl.NumberFormat(locale, { style: "currency", currency, maximumFractionDigits: 2 }).format(amount / 100);

  const row = (booking: Booking) => (
    <View key={booking.id} style={local.row}>
      <View style={local.info}>
        <Text style={[local.name, { color: palette.foreground }]}>{booking.service_name}</Text>
        <Text style={[local.meta, { color: palette.muted }]}>
          {date.format(new Date(booking.starts_at))} · {formatTime(booking.starts_at, locale, business.time_zone)}
        </Text>
      </View>
      <Text style={[local.status, { color: booking.status === "booked" ? palette.primary : palette.muted }]}>
        {booking.session_status === "cancelled" ? tStatus("sessionCancelled") : tStatus(`statuses.${booking.status}`)}
        {booking.late_cancel ? ` · ${tStatus("lateCancel")}` : ""}
      </Text>
    </View>
  );

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <Heading palette={palette}>{t("title")}</Heading>

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
      ) : data ? (
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

      <Heading palette={palette} level={2}>
        {t("upcoming")}
      </Heading>
      {data?.upcoming.length ? (
        <Card palette={palette}>{data.upcoming.map(row)}</Card>
      ) : (
        <Text style={[styles.muted, { color: palette.muted }]}>{loading ? "…" : t("noUpcoming")}</Text>
      )}
      {data?.past.length ? (
        <>
          <Heading palette={palette} level={2}>
            {t("history")}
          </Heading>
          <Card palette={palette}>{data.past.map(row)}</Card>
        </>
      ) : null}
    </Screen>
  );
}

const local = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 8 },
  info: { flex: 1, gap: 2 },
  name: { fontSize: 16, fontWeight: "600", textAlign: "left" },
  meta: { fontSize: 14, textAlign: "left" },
  status: { fontSize: 14, fontWeight: "600" },
});
