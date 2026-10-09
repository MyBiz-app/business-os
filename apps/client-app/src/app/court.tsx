import Ionicons from "@expo/vector-icons/Ionicons";
import type { components } from "@business-os/api-client";
import { addDays, dayOf, formatDay, formatTime, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Chip } from "@business-os/app-kit/components/chip";
import { PressableScale } from "@business-os/app-kit/components/motion";
import { Button, Card, ErrorText, Heading, Screen, elevation, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { tint } from "@business-os/app-kit/lib/brand";
import { newIdempotencyKey } from "@business-os/app-kit/lib/idempotency";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Service = components["schemas"]["ResourceService"];
type Slot = components["schemas"]["ResourceSlot"];
type Reservation = components["schemas"]["ClientReservation"];

const DAYS = 14;
const KNOWN = ["slot_taken", "outside_hours", "length_not_offered", "health_declaration_required", "health_declaration_review"] as const;

/** Reserve a court or room by the hour: what → how long → day → court and time → pay. */
export default function Court() {
  const t = useTranslations("client.court");
  const tAppointment = useTranslations("client.appointment");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const today = business ? todayIn(business.time_zone) : "";
  const [service, setService] = useState<Service | null>(null);
  const [minutes, setMinutes] = useState<number | null>(null);
  const [room, setRoom] = useState<string | null>(null);
  const [day, setDay] = useState(today);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [key, setKey] = useState(newIdempotencyKey);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Reservation | null>(null);

  const load = useCallback(async () => {
    if (!business) return [] as Service[];
    return api.GET("/client/resources", { params: scope }).then(unwrap);
  }, [api, scope, business]);
  const { data: services } = useLoad(load);

  // One kind of court: chosen for the client.
  useEffect(() => {
    if (services?.length === 1 && !service) choose(services[0]!);
  }, [services, service]);

  useEffect(() => {
    if (!service || !minutes || !day) return;
    let stale = false;
    setSlots(null);
    setSlot(null);
    void api
      .GET("/client/resources/slots", {
        params: { ...scope, query: { service_id: service.id, date: day, minutes, ...(room ? { room_id: room } : {}) } },
      })
      .then((result) => {
        if (!stale) setSlots(result.data ?? []);
      });
    return () => {
      stale = true;
    };
  }, [api, scope, service, minutes, room, day]);

  if (!business) return null;
  const time = (iso: string) => formatTime(iso, locale, business.time_zone);
  const inApp = business.resource_payment === "app";
  const lengths = service
    ? Array.from({ length: (service.max_minutes - service.min_minutes) / service.step_minutes + 1 }, (_, i) => service.min_minutes + i * service.step_minutes)
    : [];

  function choose(next: Service) {
    setService(next);
    setMinutes(next.min_minutes);
    setRoom(null);
  }

  const reserve = async () => {
    if (!service || !slot || !minutes) return;
    setBusy(true);
    setError(null);
    const result = await api
      .POST("/client/resources/reservations", {
        params: scope,
        body: {
          service_id: service.id,
          room_id: slot.room_id,
          starts_at: slot.starts_at,
          minutes,
          pay: inApp,
          idempotency_key: inApp ? key : null,
        },
      })
      .catch(() => null);
    setBusy(false);
    if (result?.data) {
      setKey(newIdempotencyKey());
      return setDone(result.data);
    }
    const detail = (result?.error as { detail?: string } | undefined)?.detail;
    setError(KNOWN.includes(detail as (typeof KNOWN)[number]) ? t(`errors.${detail as (typeof KNOWN)[number]}`) : t("errors.generic"));
  };

  if (done && service && slot) {
    return (
      <Screen palette={palette}>
        <View style={local.done}>
          <View style={[local.check, { backgroundColor: palette.success }]}>
            <Ionicons name="checkmark" size={52} color="#ffffff" />
          </View>
          <Text accessibilityRole="header" accessibilityLiveRegion="polite" style={[local.doneTitle, { color: palette.foreground }]}>
            {t("booked")}
          </Text>
          <Text style={[styles.muted, local.center, { color: palette.muted }]}>
            {t("bookedBody", {
              service: service.name,
              room: slot.room_name,
              date: formatDay(dayOf(slot.starts_at, business.time_zone), locale, { weekday: "long", day: "numeric", month: "long" }),
              from: time(slot.starts_at),
              to: time(slot.ends_at),
            })}
          </Text>
          <Text style={[styles.muted, local.center, { color: palette.foreground }]}>
            {done.payment
              ? t("paid", { price: formatMoney(done.payment.amount, done.payment.currency, locale) })
              : t("payAtVenue", { price: formatMoney(slot.price_amount, slot.price_currency, locale) })}
          </Text>
        </View>
        {done.payment && (
          <Button label={t("receipt")} variant="secondary" palette={palette} onPress={() => router.push(`/receipt/${done.payment!.receipt_id}`)} />
        )}
        <Button label={tAppointment("toBookings")} palette={palette} onPress={() => router.replace("/bookings")} />
      </Screen>
    );
  }

  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{t("title")}</Heading>

      {!services ? (
        <ActivityIndicator color={palette.primary} />
      ) : services.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("none")}</Text>
        </Card>
      ) : (
        services.length > 1 && (
          <>
            <Text style={[local.step, { color: palette.foreground }]}>{t("what")}</Text>
            <View role="radiogroup" aria-label={t("what")} style={local.list}>
              {services.map((item) => {
                const selected = service?.id === item.id;
                return (
                  <PressableScale
                    key={item.id}
                    role="radio"
                    aria-checked={selected}
                    accessibilityLabel={`${item.name}, ${t("perHour", { price: formatMoney(item.price_per_hour, item.price_currency, locale) })}`}
                    onPress={() => choose(item)}
                    style={[
                      local.service,
                      elevation.card,
                      { backgroundColor: selected ? tint(item.color ?? palette.primary, 0.12) : palette.surface, borderColor: selected ? palette.primary : palette.border },
                    ]}
                  >
                    <View style={[local.accent, { backgroundColor: item.color ?? palette.primary }]} />
                    <View style={local.serviceInfo}>
                      <Text style={[local.serviceName, { color: palette.foreground }]}>{item.name}</Text>
                      <Text style={[styles.muted, { color: palette.muted }]}>
                        {t("perHour", { price: formatMoney(item.price_per_hour, item.price_currency, locale) })}
                      </Text>
                    </View>
                    {selected && <Ionicons name="checkmark-circle" size={24} color={palette.primary} />}
                  </PressableScale>
                );
              })}
            </View>
          </>
        )
      )}

      {service && (
        <>
          {services?.length === 1 && (
            <Text style={[styles.muted, { color: palette.muted }]}>
              {service.name} · {t("perHour", { price: formatMoney(service.price_per_hour, service.price_currency, locale) })}
            </Text>
          )}
          <Text style={[local.step, { color: palette.foreground }]}>{t("length")}</Text>
          <View role="radiogroup" aria-label={t("length")} style={local.grid}>
            {lengths.map((value) => (
              <Chip
                key={value}
                label={tAppointment("minutes", { count: value })}
                selected={minutes === value}
                onPress={() => setMinutes(value)}
                palette={palette}
              />
            ))}
          </View>

          {service.rooms.length > 1 && (
            <>
              <Text style={[local.step, { color: palette.foreground }]}>{t("where")}</Text>
              <ScrollView horizontal role="radiogroup" aria-label={t("where")} showsHorizontalScrollIndicator={false} contentContainerStyle={local.row}>
                <Chip label={t("anyCourt")} selected={room === null} onPress={() => setRoom(null)} palette={palette} />
                {service.rooms.map((item) => (
                  <Chip key={item.id} label={item.name} selected={room === item.id} onPress={() => setRoom(item.id)} palette={palette} />
                ))}
              </ScrollView>
            </>
          )}

          <Text style={[local.step, { color: palette.foreground }]}>{tAppointment("day")}</Text>
          <ScrollView horizontal role="tablist" aria-label={tAppointment("day")} showsHorizontalScrollIndicator={false} contentContainerStyle={local.row}>
            {Array.from({ length: DAYS }, (_, i) => addDays(today, i)).map((value) => (
              <Chip
                key={value}
                role="tab"
                label={formatDay(value, locale, { day: "numeric" })}
                sublabel={formatDay(value, locale, { weekday: "short" })}
                accessibilityLabel={formatDay(value, locale, { weekday: "long", day: "numeric", month: "long" })}
                selected={day === value}
                onPress={() => setDay(value)}
                palette={palette}
              />
            ))}
          </ScrollView>

          <Text style={[local.step, { color: palette.foreground }]}>{tAppointment("time")}</Text>
          <Card palette={palette}>
            {slots === null ? (
              <ActivityIndicator color={palette.primary} />
            ) : slots.length === 0 ? (
              <Text style={[styles.muted, { color: palette.muted }]}>{t("noSlots")}</Text>
            ) : (
              <View role="radiogroup" aria-label={tAppointment("time")} style={local.grid}>
                {slots.map((item) => (
                  <Chip
                    key={`${item.room_id}-${item.starts_at}`}
                    label={time(item.starts_at)}
                    sublabel={room === null && service.rooms.length > 1 ? item.room_name : undefined}
                    accessibilityLabel={`${time(item.starts_at)}, ${item.room_name}`}
                    selected={slot?.starts_at === item.starts_at && slot.room_id === item.room_id}
                    onPress={() => setSlot(item)}
                    palette={palette}
                  />
                ))}
              </View>
            )}
          </Card>

          <ErrorText message={error} palette={palette} />
          {slot && (
            <>
              <Card palette={palette}>
                <Text style={[local.serviceName, { color: palette.foreground }]}>
                  {slot.room_name} · {time(slot.starts_at)}–{time(slot.ends_at)}
                </Text>
                <Text style={{ color: palette.foreground, fontSize: 24, fontWeight: "800", textAlign: "left" }}>
                  {formatMoney(slot.price_amount, slot.price_currency, locale)}
                </Text>
                <Text style={[styles.muted, { color: palette.muted }]}>{inApp ? t("simulated") : t("venueHint")}</Text>
              </Card>
              <Button
                label={
                  inApp
                    ? t("payAndReserve", { price: formatMoney(slot.price_amount, slot.price_currency, locale) })
                    : t("reserve", { time: time(slot.starts_at) })
                }
                palette={palette}
                busy={busy}
                onPress={() => void reserve()}
              />
            </>
          )}
        </>
      )}
    </Screen>
  );
}

const local = StyleSheet.create({
  step: { fontSize: 17, fontWeight: "700", textAlign: "left" },
  list: { gap: 10 },
  service: { flexDirection: "row", alignItems: "center", gap: 12, borderWidth: 1, borderRadius: 18, padding: 14 },
  accent: { width: 4, alignSelf: "stretch", borderRadius: 2 },
  serviceInfo: { flex: 1, gap: 2 },
  serviceName: { fontSize: 16, fontWeight: "700", textAlign: "left" },
  row: { gap: 8, paddingVertical: 2 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  done: { alignItems: "center", gap: 12, paddingVertical: 32 },
  check: { width: 92, height: 92, borderRadius: 999, alignItems: "center", justifyContent: "center" },
  doneTitle: { fontSize: 26, fontWeight: "800" },
  center: { textAlign: "center" },
});
