import type { components } from "@business-os/api-client";
import { formatTime } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Button, elevation } from "@/components/ui";
import { tint } from "@/lib/brand";
import { ApiError } from "@/lib/api";
import { confirm } from "@/lib/confirm";
import { useBusiness } from "@/providers/business-provider";

export type ClientSession = components["schemas"]["ClientSession"];

const KNOWN_ERRORS = [
  "session_started",
  "already_booked",
  "session_cancelled",
  "not_found",
  "no_valid_plan",
  "health_declaration_required",
  "health_declaration_review",
] as const;

type Props = {
  session: ClientSession;
  onChange: (session: ClientSession) => void;
  /** Also show the day (for lists that span several days, like "your next booking"). */
  showDay?: boolean;
};

/** One session with its spots and the client's book / waitlist / cancel action. */
export function SessionCard({ session, onChange, showDay = false }: Props) {
  const t = useTranslations("client");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsHealth, setNeedsHealth] = useState(false);
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
    run(() => api.POST("/client/sessions/{session_id}/bookings", { params: { ...scope, path: { session_id: session.id } } }));

  const cancel = async () => {
    if (!mine) return;
    const late =
      mine.status === "booked" &&
      Date.parse(session.starts_at) - Date.now() < business.cancellation_window_minutes * 60_000;
    const ok = await confirm(
      t("cancelTitle"),
      late ? t("cancelLateMessage") : t("cancelMessage"),
      t("cancelConfirm"),
      t("keep"),
    );
    if (ok) {
      await run(() => api.POST("/client/bookings/{booking_id}/cancel", { params: { ...scope, path: { booking_id: mine.id } } }));
    }
  };

  let status: string;
  if (cancelled) status = t("sessionCancelled");
  else if (mine?.status === "waitlisted") status = t("waitlistPosition", { position: mine.waitlist_position ?? 1 });
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
            {mine ? (
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
  strike: { textDecorationLine: "line-through" },
});
