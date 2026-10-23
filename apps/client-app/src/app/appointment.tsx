import Ionicons from "@expo/vector-icons/Ionicons";
import type { components } from "@business-os/api-client";
import { addDays, formatDay, formatTime, todayIn } from "@business-os/i18n/dates";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Linking, ScrollView, StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { fixedColors, radius } from "@business-os/app-kit/lib/theme";
import { useLocale, useTranslations } from "use-intl";

import { Chip } from "@business-os/app-kit/components/chip";
import { PressableScale } from "@business-os/app-kit/components/motion";
import { BackBar } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { tint } from "@business-os/app-kit/lib/brand";
import { calendarLink } from "@business-os/app-kit/lib/client-home";
import { formatMoney } from "@business-os/app-kit/lib/money";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useAddresses } from "@/lib/use-addresses";
import { useDependents } from "@/lib/use-dependents";
import { useBusiness } from "@/providers/business-provider";

type Slot = components["schemas"]["Slot"];
type Service = components["schemas"]["AppointmentService"];

const DAYS = 14;
const KNOWN = [
  "slot_taken",
  "outside_hours",
  "no_valid_plan",
  "period_quota_reached",
  "no_show_limit",
  "health_declaration_required",
  "health_declaration_review",
  "dependent_required",
  "unknown_dependent",
  "address_required",
] as const;
const ME = "me";

/** Book a personal appointment: service → staff → day → time. */
export default function Appointment() {
  const t = useTranslations("client.appointment");
  const tCommon = useTranslations("common");
  const tWaitlist = useTranslations("client.waitlist");
  const tDependents = useTranslations("dependents");
  const tJobs = useTranslations("jobs");
  const tHome = useTranslations("client.homeCards");
  const dependents = useDependents();
  const [who, setWho] = useState<string | null>(null);
  const [where, setWhere] = useState<string | null>(null);
  const addresses = useAddresses();
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const today = business ? todayIn(business.time_zone) : "";
  const [service, setService] = useState<Service | null>(null);
  const [staff, setStaff] = useState<string | null>(null);
  const params = useLocalSearchParams<{ day?: string; service?: string; staff?: string }>();
  const [day, setDay] = useState(params.day || today);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [booked, setBooked] = useState<Slot | null>(null);

  const load = useCallback(async () => {
    if (!business) return null;
    const [services, team] = await Promise.all([
      api.GET("/client/appointments/services", { params: scope }).then(unwrap),
      api.GET("/client/appointments/staff", { params: scope }).then(unwrap),
    ]);
    return { services, team };
  }, [api, scope, business]);
  const { data } = useLoad(load);

  // "Book again" arrives with the service (and the person) from the last visit already chosen.
  useEffect(() => {
    if (service || !data || !params.service) return;
    const wanted = data.services.find((s) => s.id === params.service);
    if (!wanted) return;
    setService(wanted);
    if (params.staff && data.team.some((m) => m.user_id === params.staff)) setStaff(params.staff);
  }, [data, params.service, params.staff, service]);

  useEffect(() => {
    if (!service || !day) return;
    let stale = false;
    setSlots(null);
    setSlot(null);
    void api
      .GET("/client/appointments/slots", {
        params: { ...scope, query: { service_id: service.id, date: day, ...(staff ? { staff_user_id: staff } : {}) } },
      })
      .then((result) => {
        if (!stale) setSlots(result.data ?? []);
      });
    return () => {
      stale = true;
    };
  }, [api, scope, service, staff, day]);

  if (!business) return null;
  const time = (iso: string) => formatTime(iso, locale, business.time_zone);
  // Industries that keep pets / children: the appointment is for one of them.
  const kind = business.dependents;
  const choices = kind
    ? [
        ...dependents.map((d) => ({ id: d.id, name: d.name })),
        ...(business.dependent_required ? [] : [{ id: ME, name: tDependents("me") }]),
      ]
    : [];
  const chosen = choices.find((c) => c.id === who) ?? choices[0] ?? null;
  // An on-site service happens at one of the client's addresses (#42).
  const onSite = service?.on_site ?? false;
  const place = onSite ? (addresses.find((a) => a.id === where) ?? addresses[0] ?? null) : null;

  const book = async () => {
    if (!service || !slot) return;
    setBusy(true);
    setError(null);
    const result = await api
      .POST("/client/appointments", {
        params: scope,
        body: {
          service_id: service.id,
          staff_user_id: slot.staff_user_id,
          starts_at: slot.starts_at,
          dependent_id: chosen && chosen.id !== ME ? chosen.id : null,
          address_id: place?.id ?? null,
        },
      })
      .catch(() => null);
    setBusy(false);
    if (result?.data) return setBooked(slot);
    const detail = (result?.error as { detail?: string } | undefined)?.detail;
    setError(KNOWN.includes(detail as (typeof KNOWN)[number]) ? t(`errors.${detail as (typeof KNOWN)[number]}`) : t("errors.generic"));
  };

  if (booked && service) {
    return (
      <Screen palette={palette}>
        <View style={local.done}>
          <View style={[local.check, { backgroundColor: palette.success }]}>
            <Ionicons name="checkmark" size={52} color={fixedColors.white} />
          </View>
          <Text accessibilityRole="header" accessibilityLiveRegion="polite" style={[local.doneTitle, { color: palette.foreground }]}>
            {t("booked")}
          </Text>
          <Text style={[styles.muted, local.center, { color: palette.muted }]}>
            {t("bookedBody", {
              service: service.name,
              date: formatDay(day, locale, { weekday: "long", day: "numeric", month: "long" }),
              time: time(booked.starts_at),
              staff: booked.staff_name,
            })}
          </Text>
        </View>
        <Button label={t("toBookings")} palette={palette} onPress={() => router.replace("/bookings")} />
        <Button
          label={tHome("addToCalendar")}
          variant="secondary"
          palette={palette}
          onPress={() =>
            void Linking.openURL(
              calendarLink({
                title: `${service.name} · ${business.name}`,
                startsAt: booked.starts_at,
                endsAt: booked.ends_at,
                details: booked.staff_name,
                location: place ? [place.street, place.city].join(", ") : null,
              }),
            )
          }
        />
        <Button
          label={t("another")}
          variant="secondary"
          palette={palette}
          onPress={() => {
            setBooked(null);
            setSlot(null);
            setSlots(null);
            setService(null);
          }}
        />
      </Screen>
    );
  }

  return (
    <Screen palette={palette}>
      <BackBar palette={palette} label={tCommon("goBack")} fallback="/home" />
      <Heading palette={palette}>{t("title")}</Heading>

      <StepTitle palette={palette} n={1} label={t("service")} />
      {!data ? (
        <ActivityIndicator color={palette.primary} />
      ) : (
        <View role="radiogroup" aria-label={t("service")} style={local.list}>
          {data.services.map((item) => {
            const selected = service?.id === item.id;
            return (
              <PressableScale
                key={item.id}
                role="radio"
                aria-checked={selected}
                accessibilityLabel={`${item.name}, ${t("minutes", { count: item.duration_minutes })}`}
                onPress={() => setService(item)}
                style={[
                  local.service,
                  { backgroundColor: selected ? tint(item.color ?? palette.primary, 0.12) : palette.surface, borderColor: selected ? palette.primary : palette.border },
                ]}
              >
                <View style={[local.accent, { backgroundColor: item.color ?? palette.primary }]} />
                <View style={local.serviceInfo}>
                  <Text style={[local.serviceName, { color: palette.foreground }]}>{item.name}</Text>
                  <Text style={[styles.muted, { color: palette.muted }]}>
                    {t("minutes", { count: item.duration_minutes })}
                    {item.price_amount > 0 ? ` · ${formatMoney(item.price_amount, item.price_currency, locale)}` : ""}
                  </Text>
                </View>
                {selected && <Ionicons name="checkmark-circle" size={24} color={palette.primary} />}
              </PressableScale>
            );
          })}
        </View>
      )}

      {service && data && (
        <>
          {data.team.length > 1 && (
            <>
              <StepTitle palette={palette} n={2} label={t("staff")} />
              <ScrollView
                horizontal
                role="radiogroup"
                aria-label={t("staff")}
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={local.row}
              >
                <Chip label={t("any")} selected={staff === null} onPress={() => setStaff(null)} palette={palette} />
                {data.team.map((member) => (
                  <Chip key={member.user_id} label={member.name} selected={staff === member.user_id} onPress={() => setStaff(member.user_id)} palette={palette} />
                ))}
              </ScrollView>
            </>
          )}

          <StepTitle palette={palette} n={data.team.length > 1 ? 3 : 2} label={t("day")} />
          <ScrollView
            horizontal
            role="tablist"
            aria-label={t("day")}
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={local.row}
          >
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

          <StepTitle palette={palette} n={data.team.length > 1 ? 4 : 3} label={t("time")} />
          <Card palette={palette}>
            {slots === null ? (
              <ActivityIndicator color={palette.primary} />
            ) : slots.length === 0 ? (
              <>
                <Text style={[styles.muted, { color: palette.muted }]}>{t("noSlots")}</Text>
                {business.waitlist_appointment !== "off" && (
                  <Button label={tWaitlist("notifyMe")} variant="secondary" palette={palette} onPress={() => router.push({ pathname: "/waitlist-new", params: { service_id: service.id, day } })} />
                )}
              </>
            ) : (
              <View role="radiogroup" aria-label={t("time")} style={local.grid}>
                {slots.map((item) => (
                  <Chip
                    key={`${item.staff_user_id}-${item.starts_at}`}
                    label={time(item.starts_at)}
                    sublabel={staff === null && data.team.length > 1 ? item.staff_name : undefined}
                    accessibilityLabel={`${time(item.starts_at)}, ${item.staff_name}`}
                    selected={slot?.starts_at === item.starts_at && slot.staff_user_id === item.staff_user_id}
                    onPress={() => setSlot(item)}
                    palette={palette}
                  />
                ))}
              </View>
            )}
          </Card>

          {kind && slot && (
            <>
              <Text style={[local.step, { color: palette.foreground }]}>{tDependents("who")}</Text>
              {choices.length === 0 ? (
                <Card palette={palette}>
                  <Text style={[styles.muted, { color: palette.muted }]}>{tDependents(`addFirst.${kind}`)}</Text>
                  <Button
                    label={tDependents(`add.${kind}`)}
                    variant="secondary"
                    palette={palette}
                    onPress={() => router.push("/dependents")}
                  />
                </Card>
              ) : (
                <View role="radiogroup" aria-label={tDependents("who")} style={local.chips}>
                  {choices.map((choice) => (
                    <Chip
                      key={choice.id}
                      label={choice.name}
                      selected={chosen?.id === choice.id}
                      onPress={() => setWho(choice.id)}
                      palette={palette}
                    />
                  ))}
                </View>
              )}
            </>
          )}
          {onSite && slot && (
            <>
              <Text style={[local.step, { color: palette.foreground }]}>{tJobs("where")}</Text>
              {addresses.length > 0 && (
                <View role="radiogroup" aria-label={tJobs("where")} style={local.chips}>
                  {addresses.map((address) => (
                    <Chip
                      key={address.id}
                      label={[address.street, address.city].join(", ")}
                      selected={place?.id === address.id}
                      onPress={() => setWhere(address.id)}
                      palette={palette}
                    />
                  ))}
                </View>
              )}
              <Button label={tJobs("addAddress")} variant="secondary" palette={palette} onPress={() => router.push("/addresses")} />
            </>
          )}
          <ErrorText message={error} palette={palette} />
          {slot && service && (
            <Card palette={palette}>
              <Text style={[local.summaryTitle, { color: palette.foreground }]}>{service.name}</Text>
              <Text style={[styles.muted, { color: palette.muted }]}>
                {formatDay(day, locale, { weekday: "long", day: "numeric", month: "long" })} · {time(slot.starts_at)} · {slot.staff_name}
              </Text>
              {service.price_amount > 0 && (
                <Text style={[styles.muted, { color: palette.muted }]}>{formatMoney(service.price_amount, service.price_currency, locale)}</Text>
              )}
            </Card>
          )}
          {slot && (!kind || choices.length > 0) && (!onSite || place) && <Button label={t("confirm", { time: time(slot.starts_at) })} palette={palette} busy={busy} onPress={() => void book()} />}
        </>
      )}
    </Screen>
  );
}

/** A numbered step heading: the booking reads as a short path, service to time. */
function StepTitle({ n, label, palette }: { n: number; label: string; palette: Palette }) {
  return (
    <View style={local.stepRow}>
      <View aria-hidden style={[local.stepNo, { backgroundColor: tint(palette.primary, 0.14) }]}>
        <Text style={[local.stepNoText, { color: palette.primary }]}>{n}</Text>
      </View>
      <Text accessibilityRole="header" style={[local.step, { color: palette.foreground }]}>
        {label}
      </Text>
    </View>
  );
}

const local = StyleSheet.create({
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  step: { fontSize: 17, fontWeight: "600", textAlign: "left" },
  stepRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  stepNo: { width: 28, height: 28, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  stepNoText: { fontSize: 13, fontWeight: "600" },
  list: { gap: 10 },
  service: { flexDirection: "row", alignItems: "center", gap: 12, borderWidth: 1, borderRadius: radius.card, padding: 14 },
  accent: { width: 4, alignSelf: "stretch", borderRadius: 2 },
  serviceInfo: { flex: 1, gap: 2 },
  serviceName: { fontSize: 15, fontWeight: "600", textAlign: "left" },
  row: { gap: 8, paddingVertical: 2 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  done: { alignItems: "center", gap: 12, paddingVertical: 32 },
  check: { width: 92, height: 92, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  doneTitle: { fontSize: 24, fontWeight: "600" },
  center: { textAlign: "center" },
  summaryTitle: { fontSize: 17, fontWeight: "600", textAlign: "left" },
});
