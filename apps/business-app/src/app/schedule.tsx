import type { components } from "@business-os/api-client";
import { dayOf, formatDay, formatTime, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Badge, BackBar, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, EmptyState, ErrorText, Field, Heading, Screen } from "@business-os/app-kit/components/ui";
import { ApiError, unwrap } from "@business-os/app-kit/lib/api";
import { timeOffProblem } from "@business-os/app-kit/lib/time-off";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";

type Shift = components["schemas"]["Shift"];
type TimeOffRequest = components["schemas"]["TimeOffRequest"];

const WEEKS_AHEAD = 4;
const TONES = { pending: "primary", approved: "success", declined: "danger", cancelled: "muted" } as const;

/** The signed-in person's own shifts for the next four weeks, their time-off requests, and the
 * form to ask for days off (a manager decides on the web). */
export default function MySchedule() {
  const t = useTranslations("business.schedule");
  const locale = useLocale();
  const { api, scope, tenant, palette } = useBusiness();
  const { session: auth } = useSession();
  const userId = auth?.user.id;
  const timeZone = tenant?.time_zone ?? "UTC";
  const today = todayIn(timeZone);
  const [startsOn, setStartsOn] = useState(today);
  const [endsOn, setEndsOn] = useState(today);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const load = useCallback(async () => {
    if (!userId) return { shifts: [] as Shift[], requests: [] as TimeOffRequest[] };
    const [shifts, requests] = await Promise.all([
      api
        .GET("/shifts", { params: { ...scope, query: { start: today, days: WEEKS_AHEAD * 7, user_id: userId } } })
        .then(unwrap),
      api.GET("/time-off-requests", { params: { ...scope, query: { mine: true } } }).then(unwrap),
    ]);
    return { shifts, requests };
  }, [api, scope, userId, today]);
  const { data, loading, reload } = useLoad(load);
  if (!tenant) return null;

  const problemText = (code: string) => (t.has(`errors.${code}`) ? t(`errors.${code}`) : t("errors.generic"));

  const send = async () => {
    const problem = timeOffProblem(startsOn.trim(), endsOn.trim(), today);
    if (problem) {
      setError(problemText(problem));
      return;
    }
    setSaving(true);
    setError(null);
    setSent(false);
    try {
      unwrap(
        await api.POST("/time-off-requests", {
          params: scope,
          body: { starts_on: startsOn.trim(), ends_on: endsOn.trim(), reason: reason.trim() || null },
        }),
      );
      setSent(true);
      setReason("");
      await reload();
    } catch (caught) {
      setError(problemText(caught instanceof ApiError ? (caught.detail ?? "") : ""));
    } finally {
      setSaving(false);
    }
  };

  const cancel = async (id: string) => {
    setError(null);
    const result = await api.DELETE("/time-off-requests/{request_id}", { params: { ...scope, path: { request_id: id } } });
    if (result.error !== undefined) setError(t("errors.generic"));
    await reload();
  };

  const dayLabel = (day: string) => formatDay(day, locale, { weekday: "short", day: "numeric", month: "short" });
  const shifts = data?.shifts ?? [];
  const requests = data?.requests ?? [];

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar label={t("back")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{t("title")}</Heading>

      <SectionTitle title={t("shifts")} palette={palette} />
      {shifts.length === 0 ? (
        <EmptyState palette={palette} loading={loading} message={t("noShifts")} />
      ) : (
        shifts.map((shift) => (
          <ListRow
            key={shift.id}
            palette={palette}
            title={`${dayLabel(dayOf(shift.starts_at, timeZone))}  ${formatTime(shift.starts_at, locale, timeZone)}–${formatTime(shift.ends_at, locale, timeZone)}`}
            subtitle={[shift.location_name, shift.position].filter(Boolean).join(" · ")}
            trailing={shift.is_cover ? <Badge label={t("cover")} palette={palette} /> : undefined}
          />
        ))
      )}

      <SectionTitle title={t("requests")} palette={palette} />
      {requests.length === 0 ? (
        <EmptyState palette={palette} loading={loading} message={t("noRequests")} />
      ) : (
        requests.map((request) => (
          <Card key={request.id} palette={palette}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={{ color: palette.foreground, fontWeight: "600" }}>
                {request.starts_on === request.ends_on
                  ? dayLabel(request.starts_on)
                  : t("dates", { from: dayLabel(request.starts_on), to: dayLabel(request.ends_on) })}
              </Text>
              <Badge label={t(`status.${request.status}`)} tone={TONES[request.status]} palette={palette} />
            </View>
            {request.reason && <Text style={{ color: palette.muted }}>{request.reason}</Text>}
            {request.decision_note && <Text style={{ color: palette.muted }}>{t("note", { note: request.decision_note })}</Text>}
            {request.status === "pending" && (
              <Button label={t("cancel")} variant="secondary" palette={palette} onPress={() => void cancel(request.id)} />
            )}
          </Card>
        ))
      )}

      <SectionTitle title={t("request")} palette={palette} />
      <Card palette={palette}>
        <Field
          label={t("from")}
          palette={palette}
          value={startsOn}
          onChangeText={setStartsOn}
          autoCapitalize="none"
          style={{ writingDirection: "ltr" }}
        />
        <Field
          label={t("to")}
          palette={palette}
          value={endsOn}
          onChangeText={setEndsOn}
          autoCapitalize="none"
          style={{ writingDirection: "ltr" }}
        />
        <Field label={t("reason")} palette={palette} value={reason} onChangeText={setReason} maxLength={200} />
        <ErrorText message={error} palette={palette} />
        {sent && <Text style={{ color: palette.primary }}>{t("sent")}</Text>}
        <Button label={t("send")} palette={palette} busy={saving} onPress={() => void send()} />
      </Card>
    </Screen>
  );
}
