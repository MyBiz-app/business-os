import {
  Banknote,
  CalendarCheck,
  CalendarX,
  ClipboardList,
  Funnel,
  MessageSquare,
  StickyNote,
  type LucideIcon,
} from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import { UserText } from "@/components/bidi";
import { Card, CardHeader } from "@/components/ui/card";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { getTenant } from "@/lib/tenant";

type Props = {
  clientId: string;
  context: Awaited<ReturnType<typeof getTenant>>;
};

/** The newest events shown on the card; the endpoint pages further for anything that needs more. */
const LATEST = 100;

type Kind = "booking" | "payment" | "plan" | "message" | "note" | "lead";

const ICON: Record<Kind, LucideIcon> = {
  booking: CalendarCheck,
  payment: Banknote,
  plan: ClipboardList,
  message: MessageSquare,
  note: StickyNote,
  lead: Funnel,
};

/** One timeline of what happened to the client: visits, payments, plans, messages, notes and the
 * history of the lead they came from, newest first, grouped by day. */
export async function ActivitySection({ clientId, context }: Props) {
  const t = await getTranslations("clients.activity");
  const locale = await getLocale();
  const { tenant, api, scope } = context;
  const events = unwrap(
    await api.GET("/clients/{client_id}/activity", {
      params: {
        ...scope,
        path: { client_id: clientId },
        query: { limit: LATEST },
      },
    }),
  );

  const dayOf = new Intl.DateTimeFormat(locale, {
    dateStyle: "full",
    timeZone: tenant.time_zone,
  });
  const timeOf = new Intl.DateTimeFormat(locale, {
    timeStyle: "short",
    timeZone: tenant.time_zone,
  });
  const dayKey = new Intl.DateTimeFormat("en-CA", {
    timeZone: tenant.time_zone,
  });

  type Event = (typeof events)[number];
  const sentence = (event: Event): string => {
    const title = event.title ?? "";
    switch (event.kind) {
      case "booking":
        return t(`booking.${event.status as "booked" | "checked_in" | "no_show" | "cancelled" | "waitlisted"}`, {
          title,
        });
      case "payment": {
        const amount = formatMoney(event.amount ?? 0, event.currency ?? tenant.currency, locale);
        return t(`payment.${event.status as "succeeded" | "failed" | "refunded"}`, { amount });
      }
      case "plan":
        return t(`plan.${event.status as "sold" | "cancelled"}`, { title });
      case "message":
        return t("message", {
          channel: t(`channels.${event.status as "whatsapp" | "sms"}`),
        });
      case "note":
        return t("note");
      case "lead":
        return t(
          `lead.${event.status as "created" | "stage" | "note" | "call" | "message" | "meeting" | "converted"}`,
          {
            detail: event.detail ?? "",
          },
        );
    }
  };

  const days: { key: string; label: string; items: Event[] }[] = [];
  for (const event of events) {
    const at = new Date(event.occurred_at);
    const key = dayKey.format(at);
    const last = days.at(-1);
    if (last?.key === key) last.items.push(event);
    else days.push({ key, label: dayOf.format(at), items: [event] });
  }

  return (
    <Card as="section" aria-labelledby="activity-heading" className="flex flex-col gap-4">
      <CardHeader title={t("title")} titleId="activity-heading" />
      {events.length === 0 ? (
        <p className="text-sm text-muted">{t("empty")}</p>
      ) : (
        <div className="flex flex-col gap-5">
          {days.map((day) => (
            <section key={day.key} className="flex flex-col gap-2">
              <h3 className="text-xs font-semibold text-muted">{day.label}</h3>
              <ol className="flex flex-col divide-y divide-border">
                {day.items.map((event) => {
                  const Icon = event.kind === "booking" && event.status === "cancelled" ? CalendarX : ICON[event.kind];
                  const note =
                    event.kind === "note" ||
                    event.kind === "message" ||
                    (event.kind === "lead" && event.status === "note");
                  return (
                    <li key={event.id} className="flex items-start gap-3 py-2.5">
                      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-muted" />
                      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                        <p className="text-sm font-medium">
                          {sentence(event)}
                          {event.kind === "payment" && event.title && (
                            <span className="font-normal text-muted"> · {t("paymentFor", { title: event.title })}</span>
                          )}
                        </p>
                        {note && event.detail && (
                          <p className="line-clamp-3 text-sm text-muted">
                            <UserText>{event.detail}</UserText>
                          </p>
                        )}
                      </div>
                      <time dateTime={event.occurred_at} className="shrink-0 text-xs tabular-nums text-muted" dir="ltr">
                        {timeOf.format(new Date(event.occurred_at))}
                      </time>
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
          {events.length >= LATEST && <p className="text-xs text-muted">{t("latest", { count: LATEST })}</p>}
        </div>
      )}
    </Card>
  );
}
