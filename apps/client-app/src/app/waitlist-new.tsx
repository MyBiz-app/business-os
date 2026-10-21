import { addDays, formatDay, todayIn } from "@business-os/i18n/dates";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Chip } from "@business-os/app-kit/components/chip";
import { RangeSlider } from "@business-os/app-kit/components/range-slider";
import { BackBar } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useLocations } from "@/lib/use-locations";
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
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const params = useLocalSearchParams<{ service_id?: string; day?: string }>();
  const today = business ? todayIn(business.time_zone) : "";
  const [serviceId, setServiceId] = useState<string | null>(params.service_id ?? null);
  const [day, setDay] = useState(params.day || today);
  const [mode, setMode] = useState<Mode>("day");
  const [from, setFrom] = useState(9 * 60);
  const [to, setTo] = useState(12 * 60);
  const [staffId, setStaffId] = useState<string | null>(null);
  const [locationId, setLocationId] = useState<string | null>(null);
  const locations = useLocations();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!business) return null;
    const [list, team] = await Promise.all([
      api.GET("/client/appointments/services", { params: scope }).then(unwrap),
      api.GET("/client/appointments/staff", { params: scope }).then(unwrap),
    ]);
    return { list, team };
  }, [api, scope, business]);
  const { data } = useLoad(load);
  const services = data?.list;
  const team = data?.team ?? [];

  if (!business) return null;

  const submit = async () => {
    if (!serviceId) return;
    setBusy(true);
    setError(null);
    const filters = { ...(staffId ? { staff_user_id: staffId } : {}), ...(locationId ? { location_id: locationId } : {}) };
    const result = await api
      .POST("/client/waitlist", {
        params: scope,
        body:
          mode === "range"
            ? { service_id: serviceId, kind: "range", day, from_time: clock(from), to_time: clock(to), ...filters }
            : { service_id: serviceId, kind: "day", day, ...filters },
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
      <BackBar palette={palette} label={tCommon("goBack")} fallback="/waitlist" />
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
          <RangeSlider
            value={{ from, to }}
            onChange={(next) => {
              setFrom(next.from);
              setTo(next.to);
            }}
            min={0}
            max={24 * 60}
            step={STEP}
            gap={STEP}
            palette={palette}
            labels={{ from: t("from"), to: t("to") }}
            describe={clock}
          />
          <Text style={[local.summary, { color: palette.foreground }]}>{`${clock(from)} - ${clock(to)}`}</Text>
          {stepper(t("from"), from, (next) => setFrom(next), 0, to - STEP)}
          {stepper(t("to"), to, (next) => setTo(next), from + STEP, 24 * 60 - STEP)}
        </Card>
      )}

      {team.length > 0 && (
        <>
          <Heading palette={palette} level={2}>
            {t("withWhom")}
          </Heading>
          <View role="radiogroup" aria-label={t("withWhom")} style={local.chips}>
            <Chip label={t("anyone")} selected={staffId === null} onPress={() => setStaffId(null)} palette={palette} />
            {team.map((member) => (
              <Chip key={member.user_id} label={member.name} selected={staffId === member.user_id} onPress={() => setStaffId(member.user_id)} palette={palette} />
            ))}
          </View>
        </>
      )}
      {locations.length > 1 && (
        <>
          <Heading palette={palette} level={2}>
            {t("branch")}
          </Heading>
          <View role="radiogroup" aria-label={t("branch")} style={local.chips}>
            <Chip label={t("anyBranch")} selected={locationId === null} onPress={() => setLocationId(null)} palette={palette} />
            {locations.map((branch) => (
              <Chip key={branch.id} label={branch.name} selected={locationId === branch.id} onPress={() => setLocationId(branch.id)} palette={palette} />
            ))}
          </View>
        </>
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
  stepperLabel: { fontSize: 13, fontWeight: "500", textAlign: "left" },
  stepperRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  summary: { fontSize: 15, fontWeight: "600", textAlign: "center", fontVariant: ["tabular-nums"], writingDirection: "ltr" },
  time: { fontSize: 20, fontWeight: "600", fontVariant: ["tabular-nums"] },
});
