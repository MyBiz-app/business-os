import { CalendarHeart } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { unwrap } from "@/lib/api";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { formatMoney } from "@/lib/money";
import { todayIn } from "@/lib/dates";
import { getTenantFor } from "@/lib/tenant";

/** Event projects (#44): accepted quotes with an event date, soonest first, with what's left to pay. */
export default async function EventsPage() {
  const t = await getTranslations("quotes");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("clients.read");
  const events = unwrap(await api.GET("/events", { params: { ...scope, query: { start: todayIn(tenant.time_zone), days: 366 } } }));
  const when = new Intl.DateTimeFormat(locale, { weekday: "short", day: "numeric", month: "long", year: "numeric", hour: "numeric", minute: "2-digit", timeZone: tenant.time_zone });

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/quotes" className="text-sm text-primary underline-offset-4 hover:underline">{t("title")}</Link>
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <CalendarHeart aria-hidden="true" className="size-7 text-primary" />
            {t("eventsTitle")}
          </span>
        }
        description={t("eventsSubtitle")}
      />
      {events.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("noEvents")}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {events.map((event) => (
            <li key={event.id}>
              <Link href={`/quotes/${event.id}`} className="flex flex-wrap items-center justify-between gap-3 card card-hover p-5">
                <span className="flex flex-col gap-0.5">
                  <span className="font-semibold">{when.format(new Date(event.event_starts_at!))}</span>
                  <span dir="auto">{event.title} · {event.client_name}</span>
                  {event.event_place && <span dir="auto" className="text-sm text-muted">{event.event_place}</span>}
                </span>
                <span className="flex flex-col items-end text-sm">
                  <span className="font-semibold tabular-nums">{formatMoney(event.total, event.currency, locale)}</span>
                  <span className={event.total - event.paid > 0 ? "text-warning" : "text-success"}>
                    {event.total - event.paid > 0 ? t("leftToPay", { amount: formatMoney(event.total - event.paid, event.currency, locale) }) : t("fullyPaid")}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Container>
  );
}
