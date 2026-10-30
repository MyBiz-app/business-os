import type { components } from "@business-os/api-client";
import { dayOf, formatDay, formatTime, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Badge, BackBar, ListRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, EmptyState, ErrorText, Field, Heading, Screen } from "@business-os/app-kit/components/ui";
import { ApiError, unwrap } from "@business-os/app-kit/lib/api";
import { canOfferSwap, isOpenSwap } from "@business-os/app-kit/lib/shift-swaps";
import { DayStrip } from "@business-os/app-kit/components/calendar-strip";
import { timeOffProblem } from "@business-os/app-kit/lib/time-off";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useStaff } from "@/providers/staff-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";

type Shift = components["schemas"]["Shift"];
type TimeOffRequest = components["schemas"]["TimeOffRequest"];
type ShiftSwap = components["schemas"]["ShiftSwap"];
type Colleague = components["schemas"]["Colleague"];

const WEEKS_AHEAD = 4;
const TONES = { pending: "primary", approved: "success", declined: "danger", cancelled: "muted" } as const;
const SWAP_TONES = {
  pending_colleague: "primary",
  pending_manager: "primary",
  approved: "success",
  declined: "danger",
  refused: "danger",
  cancelled: "muted",
} as const;

/** The signed-in person's own shifts for the next four weeks, their shift-swap offers (made and
 * received), their time-off requests, and the form to ask for days off (a manager decides on the web). */
const NO_DAYS: ReadonlySet<string> = new Set();

export default function MySchedule() {
  const t = useTranslations("business.schedule");
  const locale = useLocale();
  const { api, scope, tenant, palette } = useStaff();
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
  const [offering, setOffering] = useState<string | null>(null);
  const [colleagueId, setColleagueId] = useState<string | null>(null);
  const [swapNote, setSwapNote] = useState("");
  const [swapBusy, setSwapBusy] = useState(false);
  const [swapError, setSwapError] = useState<string | null>(null);
  const [swapSent, setSwapSent] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!userId) return { shifts: [] as Shift[], requests: [] as TimeOffRequest[], swaps: [] as ShiftSwap[], colleagues: [] as Colleague[] };
    const [shifts, requests, swaps, colleagues] = await Promise.all([
      api
        .GET("/shifts", { params: { ...scope, query: { start: today, days: WEEKS_AHEAD * 7, user_id: userId } } })
        .then(unwrap),
      api.GET("/time-off-requests", { params: { ...scope, query: { mine: true } } }).then(unwrap),
      api.GET("/shift-swaps", { params: scope }).then(unwrap),
      api.GET("/shift-swaps/colleagues", { params: scope }).then(unwrap),
    ]);
    return { shifts, requests, swaps, colleagues };
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

  const swapProblem = (code: string) => (t.has(`swap.errors.${code}`) ? t(`swap.errors.${code}`) : t("swap.errors.generic"));

  const closeOffer = () => {
    setOffering(null);
    setColleagueId(null);
    setSwapNote("");
    setSwapError(null);
  };

  const offer = async () => {
    if (!offering || !colleagueId) return;
    setSwapBusy(true);
    setSwapError(null);
    try {
      const made = unwrap(
        await api.POST("/shift-swaps", {
          params: scope,
          body: { shift_id: offering, to_user_id: colleagueId, note: swapNote.trim() || null },
        }),
      );
      setSwapSent(t("swap.sent", { name: made.to_user_name }));
      closeOffer();
      await reload();
    } catch (caught) {
      setSwapError(swapProblem(caught instanceof ApiError ? (caught.detail ?? "") : ""));
    } finally {
      setSwapBusy(false);
    }
  };

  /** Runs one answer to a swap (accept, refuse, withdraw) and refreshes the lists. */
  const answerSwap = async (run: () => Promise<{ error?: unknown }>) => {
    setSwapError(null);
    setSwapSent(null);
    const result = await run();
    if (result.error !== undefined) setSwapError(t("swap.errors.generic"));
    await reload();
  };

  const dayLabel = (day: string) => formatDay(day, locale, { weekday: "short", day: "numeric", month: "short" });
  const shifts = data?.shifts ?? [];
  const requests = data?.requests ?? [];
  const swaps = data?.swaps ?? [];
  const colleagues = data?.colleagues ?? [];
  const incoming = swaps.filter((swap) => swap.to_user_id === userId && swap.status === "pending_colleague");
  const mine = swaps.filter((swap) => swap.from_user_id === userId);
  const swapWhen = (swap: ShiftSwap) =>
    `${dayLabel(dayOf(swap.starts_at, timeZone))}  ${formatTime(swap.starts_at, locale, timeZone)}-${formatTime(swap.ends_at, locale, timeZone)} · ${swap.location_name}`;
  const now = new Date();

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
            title={`${dayLabel(dayOf(shift.starts_at, timeZone))}  ${formatTime(shift.starts_at, locale, timeZone)}-${formatTime(shift.ends_at, locale, timeZone)}`}
            subtitle={[shift.location_name, shift.position].filter(Boolean).join(" · ")}
            trailing={shift.is_cover ? <Badge label={t("cover")} palette={palette} /> : undefined}
            onPress={canOfferSwap(shift, swaps, now) ? () => setOffering(shift.id) : undefined}
            accessibilityLabel={canOfferSwap(shift, swaps, now) ? t("swap.offer") : undefined}
          />
        ))
      )}


      {incoming.length > 0 && (
        <>
          <SectionTitle title={t("swap.incoming")} palette={palette} />
          {incoming.map((swap) => (
            <Card key={swap.id} palette={palette}>
              <Text style={{ color: palette.foreground, fontWeight: "500" }}>
                {t("swap.incomingText", { from: swap.from_user_name, when: swapWhen(swap) })}
              </Text>
              {swap.note && <Text style={{ color: palette.muted }}>{swap.note}</Text>}
              <Button
                label={t("swap.accept")}
                palette={palette}
                onPress={() => void answerSwap(() => api.POST("/shift-swaps/{swap_id}/accept", { params: { ...scope, path: { swap_id: swap.id } } }))}
              />
              <Button
                label={t("swap.refuse")}
                variant="secondary"
                palette={palette}
                onPress={() => void answerSwap(() => api.POST("/shift-swaps/{swap_id}/refuse", { params: { ...scope, path: { swap_id: swap.id } } }))}
              />
            </Card>
          ))}
        </>
      )}

      {offering && (
        <>
          <SectionTitle title={t("swap.title")} palette={palette} />
          <Card palette={palette}>
            <Text style={{ color: palette.foreground, fontWeight: "500" }}>{t("swap.pick")}</Text>
            {colleagues.length === 0 && <Text style={{ color: palette.muted }}>{t("swap.none")}</Text>}
            {colleagues.map((person) => (
              <ListRow
                key={person.user_id}
                palette={palette}
                title={person.name}
                trailing={colleagueId === person.user_id ? <Badge label="✓" tone="success" palette={palette} /> : undefined}
                onPress={() => setColleagueId(person.user_id)}
              />
            ))}
            <Field label={t("swap.note")} palette={palette} value={swapNote} onChangeText={setSwapNote} maxLength={200} />
            <ErrorText message={swapError} palette={palette} />
            <Button label={t("swap.send")} palette={palette} busy={swapBusy} disabled={!colleagueId} onPress={() => void offer()} />
            <Button label={t("swap.close")} variant="secondary" palette={palette} onPress={closeOffer} />
          </Card>
        </>
      )}

      {mine.length > 0 && (
        <>
          <SectionTitle title={t("swap.mine")} palette={palette} />
          {mine.map((swap) => (
            <Card key={swap.id} palette={palette}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                <Text style={{ color: palette.foreground, fontWeight: "500", flexShrink: 1 }}>{t("swap.to", { name: swap.to_user_name })}</Text>
                <Badge label={t(`swap.status.${swap.status}`)} tone={SWAP_TONES[swap.status]} palette={palette} />
              </View>
              <Text style={{ color: palette.muted }}>{swapWhen(swap)}</Text>
              {swap.decision_note && <Text style={{ color: palette.muted }}>{t("note", { note: swap.decision_note })}</Text>}
              {isOpenSwap(swap.status) && (
                <Button
                  label={t("swap.cancel")}
                  variant="secondary"
                  palette={palette}
                  onPress={() => void answerSwap(() => api.DELETE("/shift-swaps/{swap_id}", { params: { ...scope, path: { swap_id: swap.id } } }))}
                />
              )}
            </Card>
          ))}
        </>
      )}
      {!offering && <ErrorText message={swapError} palette={palette} />}
      {swapSent && <Text style={{ color: palette.primary }}>{swapSent}</Text>}

      <SectionTitle title={t("requests")} palette={palette} />
      {requests.length === 0 ? (
        <EmptyState palette={palette} loading={loading} message={t("noRequests")} />
      ) : (
        requests.map((request) => (
          <Card key={request.id} palette={palette}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={{ color: palette.foreground, fontWeight: "500" }}>
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
        <Text style={{ color: palette.foreground, fontWeight: "500" }}>{t("from")}</Text>
        <DayStrip
          selected={startsOn}
          today={today}
          // The last day never falls before the first.
          onSelect={(day) => {
            setStartsOn(day);
            if (endsOn < day) setEndsOn(day);
          }}
          marked={NO_DAYS}
          closed={NO_DAYS}
          palette={palette}
          todayLabel={t("today")}
          closedLabel={t("closedShort")}
        />
        <Text style={{ color: palette.foreground, fontWeight: "500" }}>{t("to")}</Text>
        <DayStrip
          selected={endsOn}
          today={today}
          onSelect={(day) => setEndsOn(day < startsOn ? startsOn : day)}
          marked={NO_DAYS}
          closed={NO_DAYS}
          palette={palette}
          todayLabel={t("today")}
          closedLabel={t("closedShort")}
        />
        <Field label={t("reason")} palette={palette} value={reason} onChangeText={setReason} maxLength={200} />
        <ErrorText message={error} palette={palette} />
        {sent && <Text style={{ color: palette.primary }}>{t("sent")}</Text>}
        <Button label={t("send")} palette={palette} busy={saving} onPress={() => void send()} />
      </Card>
    </Screen>
  );
}
