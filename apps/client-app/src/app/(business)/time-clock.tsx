import type { components } from "@business-os/api-client";
import { formatDay, formatTime, dayOf } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Badge, BackBar, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, EmptyState, ErrorText, Heading, Screen } from "@business-os/app-kit/components/ui";
import { ApiError, unwrap } from "@business-os/app-kit/lib/api";
import { entryHours, formatHours } from "@business-os/app-kit/lib/time-clock";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useStaff } from "@/providers/staff-provider";

type Entry = components["schemas"]["Entry"];

/** The signed-in person's time clock: one big button to clock in or out, linked to the shift
 * they are planned for, and their last days of clocked time. A manager fixes mistakes on the web. */
export default function TimeClock() {
  const t = useTranslations("business.timeClock");
  const locale = useLocale();
  const { api, scope, tenant, palette } = useStaff();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timeZone = tenant?.time_zone ?? "UTC";

  const load = useCallback(() => api.GET("/me/time-clock", { params: scope }).then(unwrap), [api, scope]);
  const { data, reload } = useLoad(load);
  if (!tenant) return null;

  const problem = (code: string) => (t.has(`errors.${code}`) ? t(`errors.${code}`) : t("errors.generic"));
  const press = async (path: "/me/time-clock/clock-in" | "/me/time-clock/clock-out") => {
    setBusy(true);
    setError(null);
    try {
      if (path === "/me/time-clock/clock-in") unwrap(await api.POST(path, { params: scope, body: {} }));
      else unwrap(await api.POST(path, { params: scope }));
      await reload();
    } catch (caught) {
      setError(problem(caught instanceof ApiError ? (caught.detail ?? "") : ""));
      await reload();
    } finally {
      setBusy(false);
    }
  };

  const open = data?.open_entry ?? null;
  const planned = data?.planned_shift ?? null;
  const entryTitle = (entry: Entry) =>
    `${formatDay(dayOf(entry.clock_in, timeZone), locale, { weekday: "short", day: "numeric", month: "short" })} · ${formatTime(entry.clock_in, locale, timeZone)} - ${entry.clock_out ? formatTime(entry.clock_out, locale, timeZone) : t("running")}`;

  return (
    <Screen palette={palette}>
      <BackBar label={t("back")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{t("title")}</Heading>
      <Card palette={palette}>
        {open ? (
          <>
            <Text style={{ color: palette.foreground, fontSize: 18, fontWeight: "600" }}>
              {t("clockedIn", { time: formatTime(open.clock_in, locale, timeZone) })}
            </Text>
            <Text style={{ color: palette.muted }}>{open.location_name}</Text>
          </>
        ) : (
          <>
            <Text style={{ color: palette.muted }}>{t("clockedOutHint")}</Text>
            <Text style={{ color: palette.foreground }}>
              {planned
                ? t("plannedShift", {
                    from: formatTime(planned.starts_at, locale, timeZone),
                    to: formatTime(planned.ends_at, locale, timeZone),
                    branch: planned.location_name,
                  })
                : t("noShift")}
            </Text>
          </>
        )}
        <Button
          label={open ? t("clockOut") : t("clockIn")}
          variant={open ? "secondary" : "primary"}
          palette={palette}
          busy={busy}
          disabled={!data}
          onPress={() => void press(open ? "/me/time-clock/clock-out" : "/me/time-clock/clock-in")}
        />
        <ErrorText message={error} palette={palette} />
      </Card>

      <SectionTitle title={t("thisWeek")} palette={palette} />
      {data && data.recent.length === 0 && <EmptyState message={t("empty")} palette={palette} />}
      <View>
        {(data?.recent ?? []).map((entry) => (
          <ListRow
            key={entry.id}
            title={entryTitle(entry)}
            subtitle={entry.correction_reason ? t("corrected", { reason: entry.correction_reason }) : entry.location_name}
            trailing={
              entry.clock_out ? (
                <Text style={{ color: palette.foreground }}>{formatHours(entryHours(entry.clock_in, entry.clock_out))}</Text>
              ) : (
                <Badge label={t("running")} tone="primary" palette={palette} />
              )
            }
            palette={palette}
          />
        ))}
      </View>
    </Screen>
  );
}
