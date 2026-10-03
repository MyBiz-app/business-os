import type { components } from "@business-os/api-client";
import { formatTime } from "@business-os/i18n/dates";
import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { confirm } from "@/lib/confirm";
import { useBusiness } from "@/providers/business-provider";

export type ClientSession = components["schemas"]["ClientSession"];

const KNOWN_ERRORS = ["session_started", "already_booked", "session_cancelled", "not_found", "no_valid_plan"] as const;

type Props = { session: ClientSession; onChange: (session: ClientSession) => void };

/** One session with its spots and the client's book / waitlist / cancel action. */
export function SessionCard({ session, onChange }: Props) {
  const t = useTranslations("client");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!business) return null;

  const time = `${formatTime(session.starts_at, locale, business.time_zone)}–${formatTime(session.ends_at, locale, business.time_zone)}`;
  const mine = session.my_booking;
  const cancelled = session.status === "cancelled";
  const full = session.spots_left === 0;

  const run = async (action: () => Promise<{ data?: ClientSession; error?: unknown; response: Response }>) => {
    setBusy(true);
    setError(null);
    const result = await action().catch(() => null);
    setBusy(false);
    if (result?.data) return onChange(result.data);
    const detail = (result?.error as { detail?: string } | undefined)?.detail;
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
  const label = `${session.service.name}, ${time}`;

  return (
    <View
      style={[
        styles.card,
        { backgroundColor: palette.surface, borderColor: palette.border },
        { borderStartColor: session.service.color ?? palette.primary },
      ]}
    >
      <View style={styles.row}>
        <View style={styles.info}>
          <Text style={[styles.time, { color: palette.foreground }]}>{time}</Text>
          <Text style={[styles.name, { color: palette.foreground }, cancelled && styles.strike]}>
            {session.service.name}
          </Text>
          {place ? <Text style={[styles.meta, { color: palette.muted }]}>{place}</Text> : null}
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
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderWidth: 1, borderStartWidth: 5, borderRadius: 14, padding: 14, gap: 8 },
  row: { flexDirection: "row", alignItems: "center", gap: 12 },
  info: { flex: 1, gap: 2 },
  action: { minWidth: 110 },
  time: { fontSize: 15, fontWeight: "600", fontVariant: ["tabular-nums"], textAlign: "left", writingDirection: "ltr" },
  name: { fontSize: 17, fontWeight: "700", textAlign: "left" },
  meta: { fontSize: 14, textAlign: "left" },
  bold: { fontWeight: "600" },
  strike: { textDecorationLine: "line-through" },
});
