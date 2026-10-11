import type { components } from "@business-os/api-client";
import { addDays, formatDay, formatTime, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, BackBar, ListRow, PillRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { ApiError, unwrap } from "@business-os/app-kit/lib/api";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { fullName } from "@business-os/app-kit/lib/names";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Service = components["schemas"]["ResourceService"];
type Slot = components["schemas"]["ResourceSlot"];
type ClientListItem = components["schemas"]["ClientListItem"];

const DAYS = 7;
const KNOWN = ["slot_taken", "outside_hours", "length_not_offered", "invalid"] as const;

/** A reservation of a court or room, taken at the desk or on the phone: what, how long, day,
 * court and time, then who. */
export default function Reserve() {
  const t = useTranslations("business.reserve");
  const tResources = useTranslations("resources");
  const tBookings = useTranslations("bookings");
  const locale = useLocale();
  const { api, scope, tenant, palette } = useBusiness();
  const tenantId = tenant?.id;
  const today = tenant ? todayIn(tenant.time_zone) : "";
  const [serviceId, setServiceId] = useState<string | null>(null);
  const [minutes, setMinutes] = useState<number | null>(null);
  const [day, setDay] = useState(today);
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [search, setSearch] = useState("");
  const [matches, setMatches] = useState<ClientListItem[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!tenantId) return [] as Service[];
    return unwrap(await api.GET("/resources", { params: scope })).filter((s) => s.rooms.length > 0);
  }, [api, scope, tenantId]);
  const { data: services } = useLoad(load);
  const service = services?.find((s) => s.id === serviceId) ?? services?.[0] ?? null;
  const lengths = service
    ? Array.from({ length: (service.max_minutes - service.min_minutes) / service.step_minutes + 1 }, (_, i) => service.min_minutes + i * service.step_minutes)
    : [];
  const length = minutes && lengths.includes(minutes) ? minutes : (lengths[0] ?? null);

  useEffect(() => {
    if (!service || !length || !day) return;
    let stale = false;
    setSlots(null);
    setSlot(null);
    void api
      .GET("/resources/slots", { params: { ...scope, query: { service_id: service.id, date: day, minutes: length } } })
      .then((result) => {
        if (!stale) setSlots(result.data ?? []);
      });
    return () => {
      stale = true;
    };
  }, [api, scope, service, length, day]);

  if (!tenant) return null;
  const time = (iso: string) => formatTime(iso, locale, tenant.time_zone);

  const find = async () => {
    const page = unwrap(
      await api.GET("/clients", { params: { ...scope, query: { search: search.trim() || undefined, status: "active", limit: 15 } } }),
    );
    setMatches(page.items);
  };

  const reserve = async (client: ClientListItem) => {
    if (!service || !slot || !length) return;
    setBusy(true);
    setError(null);
    try {
      const booking = unwrap(
        await api.POST("/resources/reservations", {
          params: scope,
          body: { service_id: service.id, room_id: slot.room_id, starts_at: slot.starts_at, minutes: length, client_id: client.id },
        }),
      );
      router.replace(`/session/${booking.session_id}`);
    } catch (caught) {
      const code = caught instanceof ApiError ? caught.detail : undefined;
      const known = KNOWN.find((k) => k === code);
      setError(tResources(`errors.${known ?? "generic"}`));
    } finally {
      setBusy(false);
    }
  };

  const days = Array.from({ length: DAYS }, (_, i) => addDays(today, i)).map((value) => ({
    value,
    label: formatDay(value, locale, { day: "numeric" }),
    sublabel: value === today ? tResources("today") : formatDay(value, locale, { weekday: "short" }),
    accessibilityLabel: formatDay(value, locale, { weekday: "long", day: "numeric", month: "long" }),
  }));

  return (
    <Screen palette={palette}>
      <BackBar label={tResources("title")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{tResources("new")}</Heading>

      {services && services.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("none")}</Text>
        </Card>
      ) : (
        service && (
          <>
            {services && services.length > 1 && (
              <PillRow
                label={tResources("service")}
                palette={palette}
                value={service.id}
                onChange={(value) => {
                  setServiceId(value);
                  setMinutes(null);
                }}
                options={services.map((s) => ({ value: s.id, label: s.name }))}
              />
            )}
            <Text style={[styles.muted, { color: palette.muted }]}>
              {service.name} · {tResources("perHour", { price: formatMoney(service.price_per_hour, service.price_currency, locale) })}
            </Text>
            <SectionTitle title={tResources("length")} palette={palette} />
            <PillRow
              label={tResources("length")}
              palette={palette}
              value={String(length)}
              onChange={(value) => setMinutes(Number(value))}
              options={lengths.map((value) => ({ value: String(value), label: t("minutes", { count: value }) }))}
            />
            <SectionTitle title={t("day")} palette={palette} />
            <PillRow label={t("day")} palette={palette} value={day} onChange={setDay} options={days} />

            <SectionTitle title={t("time")} palette={palette} />
            {slots === null ? (
              <Text style={[styles.muted, { color: palette.muted }]}>…</Text>
            ) : slots.length === 0 ? (
              <Card palette={palette}>
                <Text style={[styles.muted, { color: palette.muted }]}>{tResources("noSlots")}</Text>
              </Card>
            ) : (
              [...new Set(slots.map((s) => s.room_name))].map((room) => (
                <View key={room} style={{ gap: 6 }}>
                  <Text style={{ color: palette.foreground, fontWeight: "700", textAlign: "left" }}>{room}</Text>
                  <PillRow
                    label={room}
                    palette={palette}
                    value={slot && slot.room_name === room ? slot.starts_at : ""}
                    onChange={(value) => setSlot(slots.find((s) => s.room_name === room && s.starts_at === value) ?? null)}
                    options={slots.filter((s) => s.room_name === room).map((s) => ({ value: s.starts_at, label: time(s.starts_at) }))}
                  />
                </View>
              ))
            )}

            {slot && (
              <Card palette={palette}>
                <Text style={{ color: palette.foreground, fontWeight: "700", textAlign: "left" }}>
                  {slot.room_name} · {time(slot.starts_at)}–{time(slot.ends_at)} · {formatMoney(slot.price_amount, slot.price_currency, locale)}
                </Text>
                <Field
                  label={tBookings("searchLabel")}
                  placeholder={tBookings("searchPlaceholder")}
                  palette={palette}
                  value={search}
                  onChangeText={setSearch}
                  onSubmitEditing={() => void find()}
                  returnKeyType="search"
                />
                <Button label={tBookings("search")} variant="secondary" palette={palette} onPress={() => void find()} />
                <ErrorText message={error} palette={palette} />
                {matches !== null &&
                  (matches.length === 0 ? (
                    <Text style={[styles.muted, { color: palette.muted }]}>{tResources("noClients")}</Text>
                  ) : (
                    matches.map((client) => {
                      const name = fullName(client.first_name, client.last_name);
                      return (
                        <ListRow
                          key={client.id}
                          palette={palette}
                          leading={<Avatar name={name} palette={palette} size={36} />}
                          title={name}
                          subtitle={client.phone}
                          accessibilityLabel={t("reserveFor", { name })}
                          onPress={() => void reserve(client)}
                          trailing={busy ? <Text style={{ color: palette.muted }}>…</Text> : undefined}
                        />
                      );
                    })
                  ))}
              </Card>
            )}
          </>
        )
      )}
    </Screen>
  );
}
