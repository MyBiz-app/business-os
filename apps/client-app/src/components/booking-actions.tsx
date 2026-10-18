import type { components } from "@business-os/api-client";
import { useState } from "react";
import { Linking, StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { ActionPill } from "@business-os/app-kit/components/action-pill";
import { ErrorText } from "@business-os/app-kit/components/ui";
import { calendarLink, isLateCancel } from "@business-os/app-kit/lib/client-home";
import { confirm } from "@business-os/app-kit/lib/confirm";
import { googleMapsLink } from "@business-os/app-kit/lib/maps";
import { useBusiness } from "@/providers/business-provider";

type Booking = components["schemas"]["ClientBooking"];

/** Navigate, add to the phone's calendar and cancel for one upcoming booking. */
export function BookingActions({
  booking,
  address,
  onChange,
  only,
}: {
  booking: Booking;
  /** Where the booking takes place, when known (enables "Navigate"). */
  address?: string | null;
  onChange: () => void;
  /** Just the cancel action (a waitlist spot has nowhere to navigate yet). */
  only?: "cancel";
}) {
  const t = useTranslations("client");
  const tHome = useTranslations("client.homeCards");
  const { api, scope, business, palette } = useBusiness();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  if (!business) return null;

  /** What cancelling now would do, from the business's cancellation policy (the server decides). */
  const warning = async (): Promise<string> => {
    const preview = await api
      .GET("/client/bookings/{booking_id}/cancel-preview", { params: { ...scope, path: { booking_id: booking.id } } })
      .then((r) => r.data)
      .catch(() => undefined);
    if (!preview) {
      const late = isLateCancel(booking.starts_at, business.cancellation_window_minutes, Date.now());
      return late ? t("cancelLateMessage") : t("cancelMessage");
    }
    if (preview.outcome === "free") return t("cancelMessage");
    if (preview.outcome === "recorded") return t("cancelLateRecorded");
    if (preview.period_quota && preview.period_unit) {
      return t("cancelLateQuota", { count: preview.period_quota, unit: preview.period_unit, used: preview.period_used ?? 0 });
    }
    if (preview.plan_kind === "punch_card") return t("cancelLateCard", { plan: preview.plan_name ?? "" });
    return t("cancelLateCounts");
  };

  const cancel = async () => {
    setBusy(true);
    const message = await warning();
    setBusy(false);
    const ok = await confirm(t("cancelTitle"), message, t("cancelConfirm"), t("keep"));
    if (!ok) return;
    setBusy(true);
    setFailed(false);
    const result = await api
      .POST("/client/bookings/{booking_id}/cancel", { params: { ...scope, path: { booking_id: booking.id } } })
      .catch(() => null);
    setBusy(false);
    if (result?.data) onChange();
    else setFailed(true);
  };

  return (
    <View style={local.row}>
      {address && !only ? (
        <ActionPill label={tHome("navigate")} icon="navigate-outline" palette={palette} onPress={() => void Linking.openURL(googleMapsLink(address))} />
      ) : null}
      {!only && (
        <ActionPill
          label={tHome("addToCalendar")}
          icon="calendar-outline"
          palette={palette}
          onPress={() =>
            void Linking.openURL(
              calendarLink({ title: `${booking.service_name} · ${business.name}`, startsAt: booking.starts_at, endsAt: booking.ends_at, location: address }),
            )
          }
        />
      )}
      <ActionPill label={only ? t("leaveWaitlist") : t("cancelBooking")} icon="close-circle-outline" tone="danger" palette={palette} busy={busy} onPress={() => void cancel()} />
      <ErrorText message={failed ? tHome("cancelFailed") : null} palette={palette} />
    </View>
  );
}

const local = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
});
