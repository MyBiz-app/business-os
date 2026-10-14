import Ionicons from "@expo/vector-icons/Ionicons";
import type { components } from "@business-os/api-client";
import { addDays, dayOf, formatDay, formatTime, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Chip } from "@business-os/app-kit/components/chip";
import { PressableScale } from "@business-os/app-kit/components/motion";
import { Button, Card, ErrorText, Heading, Screen, elevation, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { tint } from "@business-os/app-kit/lib/brand";
import { newIdempotencyKey } from "@business-os/app-kit/lib/idempotency";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { defaultTime, groupByCourt, rentalLengths, splitOffset, timeOptions } from "@/lib/court-search";
import { useBusiness } from "@/providers/business-provider";

type Service = components["schemas"]["ResourceService"];
type Slot = components["schemas"]["ResourceSlot"];
type Reservation = components["schemas"]["ClientReservation"];
type Suggestions = components["schemas"]["ResourceSuggestions"];

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
  const [day, setDay] = useState(today);
  const [at, setAt] = useState(() => defaultTime(business?.time_zone ?? "UTC"));
  const [found, setFound] = useState<Suggestions | null>(null);
  const [showGrid, setShowGrid] = useState(false);
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

  // "When suits you?": the exact slot, or the nearest free ones.
  useEffect(() => {
    if (!service || !minutes || !day) return;
    let stale = false;
    setFound(null);
    setSlot(null);
    void api
      .GET("/client/resources/suggestions", {
        params: { ...scope, query: { service_id: service.id, date: day, time: at, minutes, limit: 5 } },
      })
      .then((result) => {
        if (!stale) setFound(result.data ?? { requested_starts_at: "", exact: [], suggestions: [] });
      });
    return () => {
      stale = true;
    };
  }, [api, scope, service, minutes, day, at]);

  // The optional courts-by-hours grid for the chosen day.
  useEffect(() => {
    if (!showGrid || !service || !minutes || !day) return;
    let stale = false;
    setSlots(null);
    void api
      .GET("/client/resources/slots", { params: { ...scope, query: { service_id: service.id, date: day, minutes } } })
      .then((result) => {
        if (!stale) setSlots(result.data ?? []);
      });
    return () => {
      stale = true;
    };
  }, [api, scope, service, minutes, day, showGrid]);

  if (!business) return null;
  const time = (iso: string) => formatTime(iso, locale, business.time_zone);
  const inApp = business.resource_payment === "app";
  const lengths = service ? rentalLengths(service) : [];
  const zone = business.time_zone;
  const sameSlot = (a: Slot | null, b: Slot) => a?.starts_at === b.starts_at && a.room_id === b.room_id;
  const distance = (offset: number) => {
    const { hours, minutes: mins, later } = splitOffset(offset);
    const amount = hours > 0 && mins > 0 ? t("hoursMinutes", { hours, minutes: mins }) : hours > 0 ? t("hours", { count: hours }) : t("minutes", { count: mins });
    return t(later ? "later" : "earlier", { amount });
  };

  function choose(next: Service) {
    setService(next);
    setMinutes(rentalLengths(next)[0] ?? next.min_minutes);
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

          <Text style={[local.step, { color: palette.foreground }]}>{t("whenSuits")}</Text>
          <Text style={[local.label, { color: palette.muted }]}>{tAppointment("day")}</Text>
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
          <Text style={[local.label, { color: palette.muted }]}>{tAppointment("time")}</Text>
          <ScrollView horizontal role="radiogroup" aria-label={tAppointment("time")} showsHorizontalScrollIndicator={false} contentContainerStyle={local.row}>
            {timeOptions().map((value) => (
              <Chip key={value} label={value} selected={at === value} onPress={() => setAt(value)} palette={palette} />
            ))}
          </ScrollView>

          <Card palette={palette}>
            {found === null ? (
              <ActivityIndicator color={palette.primary} />
            ) : found.exact.length > 0 ? (
              <>
                <Text style={[local.serviceName, { color: palette.success }]}>{t("exactFree", { time: at })}</Text>
                <View role="radiogroup" aria-label={t("where")} style={local.grid}>
                  {found.exact.map((item) => (
                    <Chip
                      key={item.room_id}
                      label={item.room_name}
                      sublabel={`${time(item.starts_at)}–${time(item.ends_at)}`}
                      selected={sameSlot(slot, item)}
                      onPress={() => setSlot(item)}
                      palette={palette}
                    />
                  ))}
                </View>
              </>
            ) : found.suggestions.length === 0 ? (
              <Text style={[styles.muted, { color: palette.muted }]}>{t("noSlots")}</Text>
            ) : (
              <>
                <Text style={[local.serviceName, { color: palette.foreground }]}>{t("taken", { time: at })}</Text>
                <View role="radiogroup" aria-label={t("nearby")} style={local.list}>
                  {found.suggestions.map((item) => {
                    const selected = sameSlot(slot, item);
                    const otherDay = dayOf(item.starts_at, zone) !== day;
                    return (
                      <PressableScale
                        key={`${item.room_id}-${item.starts_at}`}
                        role="radio"
                        aria-checked={selected}
                        accessibilityLabel={`${time(item.starts_at)}, ${item.room_name}, ${distance(item.offset_minutes)}`}
                        onPress={() => setSlot(item)}
                        style={[
                          local.service,
                          elevation.card,
                          { backgroundColor: selected ? tint(palette.primary, 0.12) : palette.surface, borderColor: selected ? palette.primary : palette.border },
                        ]}
                      >
                        <View style={local.serviceInfo}>
                          <Text style={[local.serviceName, { color: palette.foreground }]}>
                            {otherDay ? `${formatDay(dayOf(item.starts_at, zone), locale, { weekday: "short", day: "numeric" })} · ` : ""}
                            {time(item.starts_at)}–{time(item.ends_at)}
                          </Text>
                          <Text style={[styles.muted, { color: palette.muted }]}>
                            {item.room_name} · {distance(item.offset_minutes)}
                          </Text>
                        </View>
                        {selected && <Ionicons name="checkmark-circle" size={24} color={palette.primary} />}
                      </PressableScale>
                    );
                  })}
                </View>
              </>
            )}
          </Card>

          <PressableScale
            role="button"
            aria-expanded={showGrid}
            accessibilityLabel={t("gridToggle")}
            onPress={() => setShowGrid((value) => !value)}
            style={local.toggle}
          >
            <Ionicons name={showGrid ? "chevron-up" : "grid-outline"} size={18} color={palette.primary} />
            <Text style={[local.toggleText, { color: palette.primary }]}>{showGrid ? t("gridHide") : t("gridToggle")}</Text>
          </PressableScale>
          {showGrid && (
            <Card palette={palette}>
              {slots === null ? (
                <ActivityIndicator color={palette.primary} />
              ) : slots.length === 0 ? (
                <Text style={[styles.muted, { color: palette.muted }]}>{t("noSlots")}</Text>
              ) : (
                groupByCourt(slots).map((court) => (
                  <View key={court.roomId} style={local.court}>
                    <Text style={[local.serviceName, { color: palette.foreground }]}>{court.name}</Text>
                    <View role="radiogroup" aria-label={court.name} style={local.grid}>
                      {court.slots.map((item) => (
                        <Chip
                          key={item.starts_at}
                          label={time(item.starts_at)}
                          accessibilityLabel={`${court.name}, ${time(item.starts_at)}`}
                          selected={sameSlot(slot, item)}
                          onPress={() => setSlot(item)}
                          palette={palette}
                        />
                      ))}
                    </View>
                  </View>
                ))
              )}
            </Card>
          )}

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
  label: { fontSize: 13, fontWeight: "600", textAlign: "left" },
  toggle: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 8, minHeight: 44 },
  toggleText: { fontSize: 15, fontWeight: "700" },
  court: { gap: 8, paddingVertical: 6 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  done: { alignItems: "center", gap: 12, paddingVertical: 32 },
  check: { width: 92, height: 92, borderRadius: 999, alignItems: "center", justifyContent: "center" },
  doneTitle: { fontSize: 26, fontWeight: "800" },
  center: { textAlign: "center" },
});
