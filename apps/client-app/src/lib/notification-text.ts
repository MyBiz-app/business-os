import type { components } from "@business-os/api-client";
import { formatTime } from "@business-os/i18n/dates";
import { useLocale, useTranslations } from "use-intl";

import { useBusiness } from "@/providers/business-provider";

export type Notification = components["schemas"]["Notification"];

/** The sentence for one notification ("The business booked you into Yoga on Sun 18:00"), shared
 * by the updates tab and the home screen's recent updates. */
export function useNotificationText(): (n: Notification) => string {
  const t = useTranslations("client.updates");
  const locale = useLocale();
  const { business } = useBusiness();
  const zone = business?.time_zone ?? "UTC";
  const day = new Intl.DateTimeFormat(locale, { weekday: "short", day: "numeric", month: "short", timeZone: zone });
  const when = (instant: unknown) =>
    typeof instant === "string" ? `${day.format(new Date(instant))} ${formatTime(instant, locale, zone)}` : "";
  const planDay = new Intl.DateTimeFormat(locale, { day: "numeric", month: "long", timeZone: "UTC" });

  return (n) => {
    const p = n.payload as Record<string, unknown>;
    const values = {
      service: String(p.service_name ?? ""),
      when: when(p.starts_at),
      previous: when(p.previous_starts_at),
      note: String(p.note ?? ""),
      plan: String(p.plan_name ?? ""),
      date: typeof p.ends_on === "string" ? planDay.format(new Date(`${p.ends_on}T12:00:00Z`)) : "",
    };
    if (n.kind === "booked_by_studio" && p.status === "waitlisted") return t("kinds.waitlisted_by_studio", values);
    if ((n.kind === "health_approved" || n.kind === "health_rejected") && p.note) {
      return `${t(`kinds.${n.kind}`, values)} ${t("note", values)}`;
    }
    return t(`kinds.${n.kind}`, values);
  };
}

/** An icon (Ionicons name) for the kind of update, so the list can be scanned. */
export function notificationIcon(kind: string): "calendar-outline" | "checkmark-circle-outline" | "close-circle-outline" | "heart-outline" | "card-outline" | "notifications-outline" {
  if (kind === "waitlist_spot_open") return "notifications-outline";
  if (kind.includes("cancel") || kind.includes("rejected")) return "close-circle-outline";
  if (kind.includes("health")) return "heart-outline";
  if (kind.includes("plan") || kind.includes("entitlement")) return "card-outline";
  if (kind.includes("booked") || kind.includes("promoted") || kind.includes("moved") || kind.includes("rescheduled")) return "calendar-outline";
  if (kind.includes("approved")) return "checkmark-circle-outline";
  return "notifications-outline";
}
