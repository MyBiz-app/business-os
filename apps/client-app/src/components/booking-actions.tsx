import type { components } from "@business-os/api-client";
import { useState } from "react";
import { Linking, Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import { useTranslations } from "use-intl";

import { ActionPill } from "@business-os/app-kit/components/action-pill";
import { SwipeRow } from "@business-os/app-kit/components/swipe-row";
import { ErrorText } from "@business-os/app-kit/components/ui";
import { calendarLink, isLateCancel } from "@business-os/app-kit/lib/client-home";
import { showActionMenu } from "@business-os/app-kit/lib/action-menu";
import { confirm } from "@business-os/app-kit/lib/confirm";
import { googleMapsLink } from "@business-os/app-kit/lib/maps";
import { useBusiness } from "@/providers/business-provider";

type Booking = components["schemas"]["ClientBooking"];

type Options = {
  booking: Booking;
  /** Where the booking takes place, when known (enables "Navigate"). */
  address?: string | null;
  onChange: () => void;
  /** Just the cancel action (a waitlist spot has nowhere to navigate yet). */
  only?: "cancel";
};

/** What can be done with one upcoming booking, shared by the buttons, the swipe and the long press. */
function useBookingActions({ booking, address, onChange, only }: Options) {
  const t = useTranslations("client");
  const tHome = useTranslations("client.homeCards");
  const tCommon = useTranslations("common");
  const { api, scope, business, palette } = useBusiness();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  /** What cancelling now would do, from the business's cancellation policy (the server decides). */
  const warning = async (): Promise<string> => {
    const preview = await api
      .GET("/client/bookings/{booking_id}/cancel-preview", { params: { ...scope, path: { booking_id: booking.id } } })
      .then((r) => r.data)
      .catch(() => undefined);
    if (!preview) {
      const late = isLateCancel(booking.starts_at, business?.cancellation_window_minutes ?? 0, Date.now());
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
    if (busy) return;
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

  const navigate = address && !only ? () => void Linking.openURL(googleMapsLink(address)) : null;
  const addToCalendar = only
    ? null
    : () =>
        void Linking.openURL(
          calendarLink({
            title: `${booking.service_name} · ${business?.name ?? ""}`,
            startsAt: booking.starts_at,
            endsAt: booking.ends_at,
            location: address,
          }),
        );

  return {
    ready: !!business,
    palette,
    busy,
    failed,
    cancel,
    navigate,
    addToCalendar,
    cancelLabel: only ? t("leaveWaitlist") : t("cancelBooking"),
    labels: { navigate: tHome("navigate"), calendar: tHome("addToCalendar"), cancelFailed: tHome("cancelFailed") },
    closeLabel: tCommon("close"),
  };
}

/** Navigate, add to the phone's calendar and cancel for one upcoming booking. */
export function BookingActions(options: Options) {
  const a = useBookingActions(options);
  if (!a.ready) return null;
  return (
    <View style={local.row}>
      {a.navigate ? <ActionPill label={a.labels.navigate} icon="navigate-outline" palette={a.palette} onPress={a.navigate} /> : null}
      {a.addToCalendar ? <ActionPill label={a.labels.calendar} icon="calendar-outline" palette={a.palette} onPress={a.addToCalendar} /> : null}
      <ActionPill label={a.cancelLabel} icon="close-circle-outline" tone="danger" palette={a.palette} busy={a.busy} onPress={() => void a.cancel()} />
      <ErrorText message={a.failed ? a.labels.cancelFailed : null} palette={a.palette} />
    </View>
  );
}

/**
 * An upcoming booking as a card: the buttons below it, plus two shortcuts for the same actions:
 * swipe the card to cancel, long-press it for a menu (navigate, calendar, cancel).
 */
export function BookingCard({ children, style, ...options }: Options & { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  const a = useBookingActions(options);
  if (!a.ready) return null;
  const actions = [
    ...(a.navigate ? [{ label: a.labels.navigate, onPress: a.navigate }] : []),
    ...(a.addToCalendar ? [{ label: a.labels.calendar, onPress: a.addToCalendar }] : []),
    { label: a.cancelLabel, destructive: true, onPress: () => void a.cancel() },
  ];
  return (
    <SwipeRow label={a.cancelLabel} icon="close-circle-outline" palette={a.palette} onAction={() => void a.cancel()}>
      <Pressable
        accessible={false}
        onLongPress={() => showActionMenu(options.booking.service_name, actions, a.closeLabel)}
        delayLongPress={350}
        style={style}
      >
        {children}
        <View style={local.actions}>
          {a.navigate ? <ActionPill label={a.labels.navigate} icon="navigate-outline" palette={a.palette} onPress={a.navigate} /> : null}
          {a.addToCalendar ? <ActionPill label={a.labels.calendar} icon="calendar-outline" palette={a.palette} onPress={a.addToCalendar} /> : null}
          <ActionPill label={a.cancelLabel} icon="close-circle-outline" tone="danger" palette={a.palette} busy={a.busy} onPress={() => void a.cancel()} />
          <ErrorText message={a.failed ? a.labels.cancelFailed : null} palette={a.palette} />
        </View>
      </Pressable>
    </SwipeRow>
  );
}

const local = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
});
