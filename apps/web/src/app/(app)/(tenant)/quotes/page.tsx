import type { components } from "@business-os/api-client";
import { FileSignature, Plus } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { MonthGrid } from "@/components/calendar-board/month-grid";
import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { LinkSegmented } from "@/components/ui/link-segmented";
import { SummaryTiles } from "@/components/ui/summary-tiles";
import { unwrap } from "@/lib/api";
import { addMonths, dayOf, formatDay, formatTime, isDay, monthGrid, todayIn } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";

import { STATUS_TONE } from "./status";

const PAGE_SIZE = 50;
const MAX_SHOWN = 1000;
const CHUNK = 200; // the API's largest page
const FILTERS = ["all", "draft", "sent", "accepted", "declined", "expired"] as const;
const VIEWS = ["quotes", "events"] as const;

/** Quotes (#44) and the events they become: a slicer between the two, numbers on top, newest first. */
export default async function QuotesPage({ searchParams }: PageProps<"/quotes">) {
  const t = await getTranslations("quotes");
  const tc = await getTranslations("common");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("clients.read");
  const query = await searchParams;
  const filter = FILTERS.find((f) => f === query.status) ?? "all";
  const view = VIEWS.find((v) => v === query.view) ?? "quotes";
  const canSell = tenant.permissions.includes("sales.manage");
  const today = todayIn(tenant.time_zone);
  const anchor = isDay(query.date) ? query.date : today;
  const month = monthGrid(anchor);

  // The tiles count every quote (a summary query); the list is one status, a page at a time.
  const summary = unwrap(await api.GET("/quotes/summary", { params: scope }));
  const total = summary.reduce((sum, row) => sum + row.count, 0);
  const shown = Math.min(MAX_SHOWN, Math.max(PAGE_SIZE, Number(query.shown) || PAGE_SIZE));
  // One more than shown tells whether a next page exists.
  const fetched: components["schemas"]["QuoteSummary"][] = [];
  while (view === "quotes" && total > 0 && fetched.length <= shown) {
    const take = Math.min(CHUNK, shown + 1 - fetched.length);
    const chunk = unwrap(
      await api.GET("/quotes", {
        params: { ...scope, query: { status: filter === "all" ? undefined : filter, limit: take, offset: fetched.length } },
      }),
    );
    fetched.push(...chunk);
    if (chunk.length < take) break;
  }
  const hasMore = fetched.length > shown;
  const quotes = fetched.slice(0, shown);
  const rowsOf = (...statuses: string[]) => summary.filter((row) => statuses.includes(row.status));
  const countOf = (rows: typeof summary) => rows.reduce((sum, row) => sum + row.count, 0);
  const totalOf = (rows: typeof summary) => {
    const currencies = new Set(rows.map((row) => row.currency));
    return rows.length > 0 && currencies.size === 1 ? formatMoney(rows.reduce((sum, row) => sum + row.total, 0), [...currencies][0], locale) : undefined;
  };
  const won = countOf(rowsOf("accepted"));
  const lost = countOf(rowsOf("declined", "expired"));
  const decided = won + lost;
  const tiles = [
    { key: "draft", label: t("tiles.draft"), value: countOf(rowsOf("draft")), hint: totalOf(rowsOf("draft")), href: "/quotes?status=draft", active: view === "quotes" && filter === "draft" },
    { key: "sent", label: t("tiles.sent"), value: countOf(rowsOf("sent")), hint: totalOf(rowsOf("sent")), href: "/quotes?status=sent", active: view === "quotes" && filter === "sent" },
    { key: "accepted", label: t("tiles.accepted"), value: countOf(rowsOf("accepted")), hint: totalOf(rowsOf("accepted")), href: "/quotes?status=accepted", active: view === "quotes" && filter === "accepted" },
    {
      key: "closeRate",
      label: t("tiles.closeRate"),
      value: decided > 0 ? `${Math.round((won / decided) * 100)}%` : "-",
      hint: decided > 0 ? t("tiles.closeRateHint", { won, decided }) : undefined,
      href: "/quotes",
      active: false,
    },
  ];
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tenant.time_zone });
  const header = (
    <PageHeader
      title={
        <span className="flex items-center gap-3">
          <FileSignature aria-hidden="true" className="size-8 shrink-0 text-primary-ink" />
          {t("titleEvents")}
        </span>
      }
      description={t("subtitleEvents")}
      actions={
        canSell && (
          <Link href="/quotes/new" className="btn-primary px-4 py-2">
            <Plus aria-hidden="true" className="size-4" /> {t("new")}
          </Link>
        )
      }
    />
  );
  const slicer = (
    <LinkSegmented
      label={t("views.label")}
      loadingLabel={tc("loading")}
      active={view}
      options={VIEWS.map((v) => ({ key: v, label: t(`views.${v}`), href: v === "quotes" ? "/quotes" : "/quotes?view=events" }))}
    />
  );

  if (view === "events") {
    const events = unwrap(await api.GET("/events", { params: { ...scope, query: { start: month.start, days: month.days } } }));
    const inMonth = events.filter((event) => dayOf(event.event_starts_at!, tenant.time_zone).startsWith(anchor.slice(0, 7)));
    const link = (day: string) => `/quotes?view=events&date=${day}`;
    const monthName = formatDay(anchor, locale, { month: "long", year: "numeric" });
    const when = new Intl.DateTimeFormat(locale, { weekday: "short", day: "numeric", month: "long", year: "numeric", hour: "numeric", minute: "2-digit", timeZone: tenant.time_zone });
    return (
      <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
        {header}
        {slicer}
        <SummaryTiles label={t("tiles.label")} tiles={tiles} />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">{t("eventsMonth", { month: monthName })}</h2>
          <nav aria-label={monthName} className="flex gap-2">
            <Link scroll={false} href={link(addMonths(anchor, -1))} className="btn-secondary px-3 py-1.5 text-sm">{t("monthPrev")}</Link>
            <Link scroll={false} href={link(addMonths(anchor, 1))} className="btn-secondary px-3 py-1.5 text-sm">{t("monthNext")}</Link>
          </nav>
        </div>
        <MonthGrid
          start={month.start}
          days={month.days}
          month={anchor.slice(0, 7)}
          today={today}
          locale={locale}
          events={events.map((event) => ({
            id: event.id,
            href: `/quotes/${event.id}`,
            day: dayOf(event.event_starts_at!, tenant.time_zone),
            start: 0,
            end: 0,
            time: formatTime(event.event_starts_at!, locale, tenant.time_zone),
            title: event.title,
            detail: event.client_name,
            color: "var(--primary)",
            branch: null,
            cancelled: false,
          }))}
          closed={{}}
          labels={{ closed: t("calendar.closed"), more: t.raw("calendar.more") as string, empty: t("calendar.empty") }}
          dayHref={link("__day__")}
        />
        {inMonth.length === 0 ? (
          <EmptyState variant="calendar">{t("noEvents")}</EmptyState>
        ) : (
          <ul className="flex flex-col gap-3">
            {inMonth.map((event) => (
              <li key={event.id}>
                <Link href={`/quotes/${event.id}`} className="flex flex-wrap items-center justify-between gap-3 card card-hover p-5">
                  <span className="flex flex-col gap-0.5">
                    <span className="font-semibold">{when.format(new Date(event.event_starts_at!))}</span>
                    <span dir="auto">{event.title} · {event.client_name}</span>
                    {event.event_place && <span dir="auto" className="text-sm text-muted">{event.event_place}</span>}
                  </span>
                  <span className="flex flex-col items-end text-sm">
                    <span className="font-semibold tabular-nums">{formatMoney(event.total, event.currency, locale)}</span>
                    <span className={event.total - event.paid > 0 ? "text-warning" : "text-success-ink"}>
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

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      {header}
      {slicer}
      {total === 0 ? (
        <section aria-labelledby="first-quote" className="card flex flex-col items-center gap-6 p-8 text-center">
          <h2 id="first-quote" className="text-xl font-semibold">{t("empty.title")}</h2>
          <ol className="grid w-full max-w-4xl gap-4 text-start sm:grid-cols-3">
            {([1, 2, 3] as const).map((step) => (
              <li key={step} className="flex flex-col gap-1 rounded-2xl border border-border p-4">
                <span className="flex size-8 items-center justify-center rounded-full bg-primary/10 font-bold text-primary-ink">{step}</span>
                <span className="font-semibold">{t(`empty.step${step}`)}</span>
                <span className="text-sm text-muted">{t(`empty.step${step}Body`)}</span>
              </li>
            ))}
          </ol>
          {canSell && (
            <div className="flex flex-wrap justify-center gap-2">
              <Link href="/quotes/new" className="btn-primary px-4 py-2">
                <Plus aria-hidden="true" className="size-4" /> {t("empty.first")}
              </Link>
              <Link href="/quotes/new?example=1" className="btn-secondary px-4 py-2">{t("empty.example")}</Link>
            </div>
          )}
        </section>
      ) : (
        <>
          <SummaryTiles label={t("tiles.label")} tiles={tiles} />
          <LinkSegmented
            variant="chips"
            label={t("filter")}
            loadingLabel={tc("loading")}
            active={filter}
            options={FILTERS.map((f) => ({ key: f, label: t(`filters.${f}`), href: f === "all" ? "/quotes" : `/quotes?status=${f}` }))}
          />
          {quotes.length === 0 ? (
            <EmptyState variant="list">{t("none")}</EmptyState>
          ) : (
            <ul className="flex flex-col divide-y divide-border card">
              {quotes.map((quote) => (
                <li key={quote.id}>
                  <Link href={`/quotes/${quote.id}`} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 hover:bg-foreground/[0.03]">
                    <span className="flex min-w-0 flex-col gap-0.5">
                      <span className="font-semibold">
                        <span className="tabular-nums text-muted">#{quote.number}</span> <span dir="auto">{quote.title}</span>
                      </span>
                      <span className="text-sm text-muted">
                        <span dir="auto">{quote.client_name}</span> · {date.format(new Date(quote.created_at))}
                        {quote.event_starts_at && ` · ${t("eventOn", { date: date.format(new Date(quote.event_starts_at)) })}`}
                      </span>
                    </span>
                    <span className="flex items-center gap-3">
                      <span className="font-semibold tabular-nums">{formatMoney(quote.total, quote.currency, locale)}</span>
                      <Pill tone={STATUS_TONE[quote.status]}>{t(`statuses.${quote.status}`)}</Pill>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {hasMore && shown < MAX_SHOWN && (
            <Link
              scroll={false}
              href={`/quotes?${filter === "all" ? "" : `status=${filter}&`}shown=${shown + PAGE_SIZE}`}
              className="btn-secondary self-center px-4 py-2"
            >
              {t("loadMore")}
            </Link>
          )}
        </>
      )}
    </Container>
  );
}
