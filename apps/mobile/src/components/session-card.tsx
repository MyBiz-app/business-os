import type { components } from "@business-os/api-client";
import { formatTime } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Chip } from "@business-os/app-kit/components/chip";
import { Button, elevation } from "@business-os/app-kit/components/ui";
import { tint } from "@business-os/app-kit/lib/brand";
import { ApiError } from "@business-os/app-kit/lib/api";
import { confirm } from "@business-os/app-kit/lib/confirm";
import { useBusiness } from "@/providers/business-provider";

export type ClientSession = components["schemas"]["ClientSession"];
type Dependent = components["schemas"]["Dependent"];

const ME = "me";

const KNOWN_ERRORS = [
  "session_started",
  "already_booked",
  "session_cancelled",
  "not_found",
  "no_valid_plan",
  "health_declaration_required",
  "health_declaration_review",
  "dependent_required",
  "unknown_dependent",
] as const;

type Props = {
  session: ClientSession;
  onChange: (session: ClientSession) => void;
  /** Also show the day (for lists that span several days, like "your next booking"). */
  showDay?: boolean;
  /** The client's active pets / children, in industries that keep them: a booking is for one. */
  dependents?: Dependent[];
};

/** One session with its spots and the client's book / waitlist / cancel action. */
export function SessionCard({ session, onChange, showDay = false, dependents = [] }: Props) {
  const t = useTranslations("client");
  const tDependents = useTranslations("dependents");
  const tJobs = useTranslations("jobs");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsHealth, setNeedsHealth] = useState(false);
  const [who, setWho] = useState<string | null>(null);
  if (!business) return null;

  const hours = `${formatTime(session.starts_at, locale, business.time_zone)}–${formatTime(session.ends_at, locale, business.time_zone)}`;
  const day = showDay
    ? new Intl.DateTimeFormat(locale, {
        weekday: "short",
        day: "numeric",
        month: "short",
        timeZone: business.time_zone,
      }).format(new Date(session.starts_at))
    : null;
  const time = hours;
  const mine = session.my_booking;
  const cancelled = session.status === "cancelled";
  const full = session.spots_left === 0;
  // Industries that keep pets / children: each booking is for one of them (or the client).
  const kind = business.dependents;
  const mineAll = session.my_bookings ?? [];
  const taken = new Set(mineAll.map((b) => b.dependent_id ?? ME));
  const choices = kind
    ? [
        ...dependents.filter((d) => !taken.has(d.id)).map((d) => ({ id: d.id, name: d.name })),
        ...(business.dependent_required || taken.has(ME) ? [] : [{ id: ME, name: tDependents("me") }]),
      ]
    : [];
  const chosen = choices.find((c) => c.id === who) ?? choices[0] ?? null;

  const run = async (action: () => Promise<{ data?: ClientSession; error?: unknown; response: Response }>) => {
    setBusy(true);
    setError(null);
    setNeedsHealth(false);
    const result = await action().catch(() => null);
    setBusy(false);
    if (result?.data) return onChange(result.data);
    const detail = (result?.error as { detail?: string } | undefined)?.detail;
    setNeedsHealth(detail === "health_declaration_required");
    setError(
      KNOWN_ERRORS.includes(detail as (typeof KNOWN_ERRORS)[number])
        ? t(`errors.${detail as (typeof KNOWN_ERRORS)[number]}`)
        : t("errors.generic"),
    );
  };

  const book = () =>
    run(() =>
      api.POST("/client/sessions/{session_id}/bookings", {
        params: { ...scope, path: { session_id: session.id } },
        body: { dependent_id: chosen && chosen.id !== ME ? chosen.id : null },
      }),
    );

  const cancel = async (booking = mine) => {
    if (!booking) return;
    const late =
      booking.status === "booked" &&
      Date.parse(session.starts_at) - Date.now() < business.cancellation_window_minutes * 60_000;
    const ok = await confirm(
      t("cancelTitle"),
      late ? t("cancelLateMessage") : t("cancelMessage"),
      t("cancelConfirm"),
      t("keep"),
    );
    if (ok) {
      await run(() => api.POST("/client/bookings/{booking_id}/cancel", { params: { ...scope, path: { booking_id: booking.id } } }));
    }
  };

  let status: string;
  if (cancelled) status = t("sessionCancelled");
  else if (mine?.status === "waitlisted") status = t("waitlistPosition", { position: mine.waitlist_position ?? 1 });
  else if (mine && session.job_status && session.job_status !== "scheduled")
    status = tJobs(`clientStatus.${session.job_status}`);
  else if (kind && mineAll.some((b) => b.dependent_name))
    status = tDependents("booked", { names: mineAll.map((b) => b.dependent_name ?? tDependents("me")).join(", ") });
  else if (mine) status = t("youreBooked");
  else if (full) status = t("full", { count: session.waitlisted });
  else status = t("spotsLeft", { count: session.spots_left });

  const place = [session.location_name, session.room_name].filter(Boolean).join(" · ");
  const color = session.service.color ?? palette.primary;
  const fill = session.capacity ? Math.min((session.capacity - session.spots_left) / session.capacity, 1) : 0;
  const label = `${session.service.name}, ${day ? `${day} ` : ""}${time}`;

  return (
    <View
      style={[
        styles.card,
        elevation.card,
        { backgroundColor: palette.surface, borderColor: mine && !cancelled ? palette.primary : palette.border },
      ]}
    >
      <View style={styles.row}>
        <View aria-hidden style={[styles.accent, { backgroundColor: color }]} />
        <View style={styles.info}>
          <View style={styles.when}>
            {day && <Text style={[styles.day, { color: palette.foreground }]}>{day}</Text>}
            <View style={[styles.timeChip, { backgroundColor: tint(color, 0.14) }]}>
              <Text style={[styles.time, { color: palette.foreground }]}>{time}</Text>
            </View>
          </View>
          <Text style={[styles.name, { color: palette.foreground }, cancelled && styles.strike]}>
            {session.service.name}
          </Text>
          {place ? <Text style={[styles.meta, { color: palette.muted }]}>{place}</Text> : null}
          {/* An on-site job (#42): where the technician comes. */}
          {session.address ? <Text style={[styles.meta, { color: palette.muted }]}>{session.address}</Text> : null}
          {/* Spots matter for group sessions; a 1:1 appointment has none to show. */}
          {!cancelled && session.capacity > 1 && (
            <View aria-hidden style={[styles.bar, { backgroundColor: tint(palette.muted, 0.18) }]}>
              <View style={[styles.barFill, { width: `${fill * 100}%`, backgroundColor: color }]} />
            </View>
          )}
          <Text
            accessibilityLiveRegion="polite"
            style={[styles.meta, { color: mine ? palette.primary : palette.muted }, mine && styles.bold]}
          >
            {status}
          </Text>
        </View>
        {!cancelled && (
          <View style={styles.action}>
            {kind ? (
              choices.length > 0 ? (
                <Button
                  label={full ? t("joinWaitlist") : t("book")}
                  accessibilityLabel={`${full ? t("joinWaitlist") : t("book")} – ${label}${chosen ? ` – ${chosen.name}` : ""}`}
                  variant={full ? "secondary" : "primary"}
                  palette={palette}
                  busy={busy}
                  onPress={() => void book()}
                />
              ) : !mine ? (
                <Button
                  label={tDependents(`add.${kind}`)}
                  variant="secondary"
                  palette={palette}
                  onPress={() => router.push("/dependents")}
                />
              ) : null
            ) : mine ? (
              <Button
                label={mine.status === "waitlisted" ? t("leaveWaitlist") : t("cancelBooking")}
                accessibilityLabel={`${mine.status === "waitlisted" ? t("leaveWaitlist") : t("cancelBooking")} – ${label}`}
                variant="danger"
                palette={palette}
                busy={busy}
                onPress={() => void cancel()}
              />
            ) : (
              <Button
                label={full ? t("joinWaitlist") : t("book")}
                accessibilityLabel={`${full ? t("joinWaitlist") : t("book")} – ${label}`}
                variant={full ? "secondary" : "primary"}
                palette={palette}
                busy={busy}
                onPress={() => void book()}
              />
            )}
          </View>
        )}
      </View>
      {kind && !cancelled && choices.length > 1 && (
        <View role="radiogroup" aria-label={tDependents("who")} style={styles.who}>
          <Text style={[styles.meta, { color: palette.muted }]}>{tDependents("who")}</Text>
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
      {kind && !cancelled && choices.length === 0 && !mine && (
        <Text style={[styles.meta, { color: palette.muted }]}>{tDependents(`addFirst.${kind}`)}</Text>
      )}
      {kind &&
        !cancelled &&
        mineAll.map((booking) => {
          const name = booking.dependent_name ?? tDependents("me");
          const action = booking.status === "waitlisted" ? t("leaveWaitlist") : t("cancelBooking");
          return (
            <View key={booking.id} style={styles.mineRow}>
              <Text style={[styles.meta, styles.bold, { color: palette.primary, flex: 1 }]}>
                {name}
                {booking.status === "waitlisted" ? ` · ${t("waitlistPosition", { position: booking.waitlist_position ?? 1 })}` : ""}
              </Text>
              <View style={styles.action}>
                <Button
                  label={action}
                  accessibilityLabel={`${action} – ${label} – ${name}`}
                  variant="danger"
                  palette={palette}
                  busy={busy}
                  onPress={() => void cancel(booking)}
                />
              </View>
            </View>
          );
        })}
      {error && (
        <Text accessibilityRole="alert" style={[styles.meta, { color: palette.danger }]}>
          {error}
        </Text>
      )}
      {needsHealth && (
        <Button label={t("health.fill")} variant="secondary" palette={palette} onPress={() => router.push("/health")} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderWidth: 1, borderRadius: 20, padding: 14, gap: 8 },
  accent: { alignSelf: "stretch", width: 4, borderRadius: 2 },
  timeChip: { alignSelf: "flex-start", borderRadius: 8, paddingHorizontal: 8, paddingVertical: 2 },
  bar: { height: 4, borderRadius: 2, overflow: "hidden", marginTop: 6, marginBottom: 2, maxWidth: 180 },
  barFill: { height: "100%", borderRadius: 2 },
  row: { flexDirection: "row", alignItems: "center", gap: 12 },
  info: { flex: 1, gap: 2, alignItems: "stretch" },
  action: { minWidth: 110 },
  time: { fontSize: 15, fontWeight: "600", fontVariant: ["tabular-nums"], textAlign: "left", writingDirection: "ltr" },
  when: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 6, marginBottom: 4 },
  day: { fontSize: 14, fontWeight: "600", textAlign: "left" },
  name: { fontSize: 17, fontWeight: "700", textAlign: "left" },
  meta: { fontSize: 14, textAlign: "left" },
  bold: { fontWeight: "600" },
  who: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 },
  mineRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  strike: { textDecorationLine: "line-through" },
});
