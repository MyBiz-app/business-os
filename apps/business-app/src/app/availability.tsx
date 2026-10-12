import { formatDay } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { BackBar, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Field, Heading, Screen } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { type AvailabilityDraft, availabilityProblem, normalizeTime, weekdayOrder } from "@business-os/app-kit/lib/availability";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Row = AvailabilityDraft & { key: number };

let nextKey = 0;
const row = (w: AvailabilityDraft): Row => ({ ...w, starts: w.starts.slice(0, 5), ends: w.ends.slice(0, 5), key: nextKey++ });

/** The signed-in person's week: the hours they can work shifts. Managers see it on the shift
 * board, which warns when a shift falls outside it and suggests who can fill a gap. */
export default function MyAvailability() {
  const t = useTranslations("business.availability");
  const locale = useLocale();
  const { api, scope, tenant, palette } = useBusiness();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = useCallback(() => api.GET("/me/availability", { params: scope }).then(unwrap), [api, scope]);
  const { data } = useLoad(load);
  useEffect(() => {
    if (data) setRows(data.windows.map(row));
  }, [data]);
  if (!tenant) return null;

  const change = (next: Row[]) => {
    setRows(next);
    setSaved(false);
  };
  const update = (key: number, field: "starts" | "ends", value: string) => change((rows ?? []).map((r) => (r.key === key ? { ...r, [field]: value } : r)));

  const save = async () => {
    const week = (rows ?? []).map(({ weekday, starts, ends }) => ({ weekday, starts: normalizeTime(starts), ends: normalizeTime(ends) }));
    const problem = availabilityProblem(week);
    if (problem) {
      setError(t(`errors.${problem}`));
      return;
    }
    setSaving(true);
    setError(null);
    const result = await api.PUT("/me/availability", { params: scope, body: { windows: week } });
    setSaving(false);
    if (result.error !== undefined) {
      setError(t("errors.generic"));
      return;
    }
    setRows(result.data.windows.map(row));
    setSaved(true);
  };

  // Sunday first where the business's week starts on Sunday (Hebrew).
  const order = weekdayOrder(locale === "he");
  return (
    <Screen palette={palette}>
      <BackBar label={t("back")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{t("title")}</Heading>
      <Text style={{ color: palette.muted }}>{t("hint")}</Text>

      {rows &&
        order.map((weekday) => {
          const today = rows.filter((r) => r.weekday === weekday);
          return (
            <View key={weekday}>
              <SectionTitle title={formatDay(`2024-01-0${weekday + 1}`, locale, { weekday: "long" })} palette={palette} />
              <Card palette={palette}>
                {today.length === 0 && <Text style={{ color: palette.muted }}>{t("none")}</Text>}
                {today.map((r) => (
                  <View key={r.key} style={{ gap: 8 }}>
                    <View style={{ flexDirection: "row", gap: 12 }}>
                      <View style={{ flex: 1 }}>
                        <Field label={t("from")} palette={palette} value={r.starts} onChangeText={(v) => update(r.key, "starts", v)} placeholder="08:00" autoCapitalize="none" keyboardType="numbers-and-punctuation" maxLength={5} style={{ writingDirection: "ltr" }} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Field label={t("to")} palette={palette} value={r.ends} onChangeText={(v) => update(r.key, "ends", v)} placeholder="16:00" autoCapitalize="none" keyboardType="numbers-and-punctuation" maxLength={5} style={{ writingDirection: "ltr" }} />
                      </View>
                    </View>
                    <Button label={t("remove")} variant="secondary" palette={palette} onPress={() => change(rows.filter((x) => x.key !== r.key))} />
                  </View>
                ))}
                <Button label={t("add")} variant="secondary" palette={palette} onPress={() => change([...rows, row({ weekday, starts: "08:00", ends: "16:00" })])} />
              </Card>
            </View>
          );
        })}

      <Text style={{ color: palette.muted }}>{t("endHint")}</Text>
      <ErrorText message={error} palette={palette} />
      {saved && <Text style={{ color: palette.primary }}>{t("saved")}</Text>}
      <Button label={t("save")} palette={palette} busy={saving} disabled={!rows} onPress={() => void save()} />
    </Screen>
  );
}
