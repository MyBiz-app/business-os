import { getFormatter, getTranslations } from "next-intl/server";

import { EmptyState } from "@/components/empty-state";
import { UserText } from "@/components/bidi";
import { toMajor } from "@/lib/money";

type Event = { at: string; kind: string; actor: string | null; details: Record<string, unknown> };

const CHANGES = ["trial_extended", "modules_changed", "invoice_voided", "card_updated"] as const;
const INVOICE_STATUS = ["open", "paid", "void"] as const;
const REQUEST_STATUS = ["new", "in_progress", "done"] as const;

function pick<T extends string>(value: unknown, allowed: readonly T[]): T | null {
  return allowed.find((candidate) => candidate === value) ?? null;
}

/** One line per event, newest first: what happened to the business and who did it. */
export async function Timeline({ events }: { events: Event[] }) {
  const t = await getTranslations("platform.card");
  const format = await getFormatter();

  function describe(event: Event): React.ReactNode {
    const d = event.details;
    switch (event.kind) {
      case "signup":
      case "trial_ends":
      case "closed":
        return t(`events.${event.kind}`);
      case "invoice": {
        const currency = String(d.currency ?? "");
        return t("events.invoice", {
          number: Number(d.number),
          amount: format.number(toMajor(Number(d.total), currency), { style: "currency", currency }),
          status: t(`events.invoiceStatus.${pick(d.status, INVOICE_STATUS) ?? "open"}`),
        });
      }
      case "request":
        return t(d.from_business ? "events.requestFromBusiness" : "events.request", {
          status: t(`events.requestStatus.${pick(d.status, REQUEST_STATUS) ?? "new"}`),
        });
      case "note":
        return (
          <>
            <span className="font-medium">{t("events.note")}: </span>
            <UserText>{String(d.body ?? "")}</UserText>
          </>
        );
      case "change": {
        const action = String(d.action ?? "").replace("business.", "");
        const known = pick(action, CHANGES);
        return known ? t(`events.changes.${known}`, { days: Number(d.days ?? 0) }) : action;
      }
      default:
        return event.kind;
    }
  }

  if (events.length === 0) return <EmptyState variant="list">{t("noTimeline")}</EmptyState>;
  return (
    <ol className="flex flex-col divide-y divide-border">
      {events.map((event, index) => (
        <li key={`${event.kind}-${event.at}-${index}`} className="flex flex-col gap-0.5 py-3 text-sm">
          <span className="text-muted">
            {format.dateTime(new Date(event.at), { dateStyle: "medium", timeStyle: "short" })}
            {event.actor && (
              <>
                {" · "}
                <span dir="auto">{t("by", { who: event.actor })}</span>
              </>
            )}
          </span>
          <span>{describe(event)}</span>
        </li>
      ))}
    </ol>
  );
}
