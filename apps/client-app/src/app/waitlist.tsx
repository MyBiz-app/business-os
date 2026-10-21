import { formatDay, formatTime } from "@business-os/i18n/dates";
import type { components } from "@business-os/api-client";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { View, StyleSheet } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { BackBar } from "@business-os/app-kit/components/rows";
import { Button, Card, EmptyState, ErrorText, Heading, LoadError, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { newIdempotencyKey } from "@business-os/app-kit/lib/idempotency";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Entry = components["schemas"]["MyWaitlistEntry"];

/** The client's waitlists: ranges and days they asked for, places on classes, and spots to take now. */
export default function Waitlist() {
  const t = useTranslations("client.waitlist");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!business) return null;
    return api.GET("/client/waitlist", { params: scope }).then(unwrap);
  }, [api, scope, business]);
  const { data, error: loadError, loading, reload } = useLoad(load);

  if (!business) return null;
  const zone = business.time_zone;

  const describe = (entry: Entry) => {
    const day = formatDay(entry.day, locale, { weekday: "long", day: "numeric", month: "long" });
    if (entry.kind === "range" && entry.from_time && entry.to_time) return t("rangeAt", { day, from: entry.from_time.slice(0, 5), to: entry.to_time.slice(0, 5) });
    if (entry.starts_at) return t("slotAt", { day, time: formatTime(entry.starts_at, locale, zone) });
    return t("dayAt", { day });
  };

  const leave = async (entry: Entry) => {
    setBusy(entry.id);
    setError(null);
    const result =
      entry.source === "booking"
        ? await api.POST("/client/bookings/{booking_id}/cancel", { params: { ...scope, path: { booking_id: entry.id } } }).catch(() => null)
        : await api.DELETE("/client/waitlist/{request_id}", { params: { ...scope, path: { request_id: entry.id } } }).catch(() => null);
    setBusy(null);
    if (result?.error) setError(t("errors.generic"));
    else void reload();
  };

  const take = async (entry: Entry, pay = false) => {
    if (!entry.offer_session_id) return;
    setBusy(entry.id);
    setError(null);
    const result = await api
      .POST("/client/waitlist/claim", { params: scope, body: { session_id: entry.offer_session_id, pay, idempotency_key: newIdempotencyKey() } })
      .catch(() => null);
    setBusy(null);
    if (result?.data) return router.replace("/bookings");
    const detail = (result?.error as { detail?: string } | undefined)?.detail;
    if (detail === "spot_taken") setError(t("errors.spot_taken"));
    else if (detail === "payment_required") setError(t("errors.payment_required"));
    else setError(t("errors.generic"));
    void reload();
  };

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar palette={palette} label={tCommon("goBack")} fallback="/bookings" />
      <Heading palette={palette}>{t("title")}</Heading>
      {loadError !== undefined && !data && <LoadError palette={palette} onRetry={() => void reload()} />}
      <ErrorText message={error} palette={palette} />
      {data && data.length === 0 && <EmptyState palette={palette} message={t("empty")} icon="hourglass-outline" />}
      {data?.map((entry) => (
        <Card key={entry.id} palette={palette}>
          <Text style={[local.name, { color: palette.foreground }]}>{entry.service_name}</Text>
          <Text style={[styles.muted, { color: palette.muted }]}>{describe(entry)}</Text>
          {entry.position != null && <Text style={[styles.muted, { color: palette.muted }]}>{t("position", { position: entry.position })}</Text>}
          {entry.offer_session_id && entry.offer_starts_at && (
            <Text accessibilityLiveRegion="polite" style={[local.offer, { color: palette.success }]}>
              {t("spotOpen", { day: formatDay(entry.offer_starts_at.slice(0, 10), locale, { weekday: "short", day: "numeric", month: "short" }), time: formatTime(entry.offer_starts_at, locale, zone) })}
            </Text>
          )}
          <View style={local.actions}>
            {entry.offer_session_id && <Button label={t("take")} palette={palette} busy={busy === entry.id} onPress={() => void take(entry)} />}
            <Button label={t("leave")} variant="secondary" palette={palette} busy={busy === entry.id} onPress={() => void leave(entry)} />
          </View>
        </Card>
      ))}
      {(business.waitlist_appointment !== "off" || business.waitlist_resource !== "off") && (
        <Button label={t("add")} variant="secondary" palette={palette} onPress={() => router.push("/waitlist-new")} />
      )}
    </Screen>
  );
}

const local = StyleSheet.create({
  name: { fontSize: 17, fontWeight: "600", textAlign: "left" },
  offer: { fontSize: 15, fontWeight: "600", textAlign: "left" },
  actions: { gap: 8 },
});
