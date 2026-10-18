import { addDays, formatDay, todayIn } from "@business-os/i18n/dates";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Chip } from "@business-os/app-kit/components/chip";
import { Button, Card, ErrorText, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

const DAYS = 14;
const STEP = 30;
const KNOWN = ["waitlist_off", "already_waiting", "in_the_past", "too_many", "on_site"] as const;
type Mode = "day" | "range";

/** "09:30" for minutes after midnight. */
const clock = (minutes: number) => `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;

/** Ask to be told when a spot opens: a service, a day, and the whole day or a time range. */
export default function WaitlistNew() {
  const t = useTranslations("client.waitlist");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const params = useLocalSearchParams<{ service_id?: string; day?: string }>();
  const today = business ? todayIn(business.time_zone) : "";
  const [serviceId, setServiceId] = useState<string | null>(params.service_id ?? null);
  const [day, setDay] = useState(params.day || today);
  const [mode, setMode] = useState<Mode>("day");
  const [from, setFrom] = useState(9 * 60);
  const [to, setTo] = useState(12 * 60);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!business) return null;
    return api.GET("/client/appointments/services", { params: scope }).then(unwrap);
  }, [api, scope, business]);
  const { data: services } = useLoad(load);

  if (!business) return null;

  const submit = async () => {
    if (!serviceId) return;
    setBusy(true);
    setError(null);
    const result = await api
      .POST("/client/waitlist", {
        params: scope,
        body:
          mode === "range"
            ? { service_id: serviceId, kind: "range", day, from_time: clock(from), to_time: clock(to) }
            : { service_id: serviceId, kind: "day", day },
      })
      .catch(() => null);
    setBusy(false);
    if (result?.data) return router.replace("/waitlist");
    const detail = (result?.error as { detail?: string } | undefined)?.detail;
    setError(KNOWN.includes(detail as (typeof KNOWN)[number]) ? t(`errors.${detail as (typeof KNOWN)[number]}`) : t("errors.generic"));
  };

  /** A stepper for one end of the range, in 30-minute steps. */
  const stepper = (label: string, value: number, set: (next: number) => void, min: number, max: number) => (
    <View style={local.stepper}>
      <Text style={[local.stepperLabel, { color: palette.muted }]}>{label}</Text>
      <View style={local.stepperRow}>
        <Button label="-" variant="secondary" palette={palette} accessibilityLabel={t("earlier", { what: label })} disabled={value <= min} onPress={() => set(value - STEP)} />
        <Text style={[local.time, { color: palette.foreground }]}>{clock(value)}</Text>
        <Button label="+" variant="secondary" palette={palette} accessibilityLabel={t("later", { what: label })} disabled={value >= max} onPress={() => set(value + STEP)} />
      </View>
    </View>
  );

  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{t("newTitle")}</Heading>
      <Text style={[styles.muted, { color: palette.muted }]}>{t("newBody")}</Text>

      <Heading palette={palette} level={2}>
        {t("service")}
      </Heading>
      {!services ? (
        <ActivityIndicator color={palette.primary} />
      ) : (
        <View role="radiogroup" aria-label={t("service")} style={local.chips}>
          {services.map((item) => (
            <Chip key={item.id} label={item.name} selected={serviceId === item.id} onPress={() => setServiceId(item.id)} palette={palette} />
          ))}
        </View>
      )}

      <Heading palette={palette} level={2}>
        {t("day")}
      </Heading>
      <ScrollView horizontal role="tablist" aria-label={t("day")} showsHorizontalScrollIndicator={false} contentContainerStyle={local.row}>
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

      <Heading palette={palette} level={2}>
        {t("when")}
      </Heading>
      <View role="radiogroup" aria-label={t("when")} style={local.chips}>
        <Chip label={t("allDay")} selected={mode === "day"} onPress={() => setMode("day")} palette={palette} />
        <Chip label={t("range")} selected={mode === "range"} onPress={() => setMode("range")} palette={palette} />
      </View>
      {mode === "range" && (
        <Card palette={palette}>
          {stepper(t("from"), from, (next) => setFrom(next), 0, to - STEP)}
          {stepper(t("to"), to, (next) => setTo(next), from + STEP, 24 * 60 - STEP)}
        </Card>
      )}

      <ErrorText message={error} palette={palette} />
      <Button label={t("submit")} palette={palette} busy={busy} disabled={!serviceId} onPress={() => void submit()} />
    </Screen>
  );
}

const local = StyleSheet.create({
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  row: { gap: 8, paddingVertical: 2 },
  stepper: { gap: 6 },
  stepperLabel: { fontSize: 13, fontWeight: "600", textAlign: "left" },
  stepperRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  time: { fontSize: 22, fontWeight: "800", fontVariant: ["tabular-nums"] },
});
