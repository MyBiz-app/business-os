import type { components } from "@business-os/api-client";
import { FileSignature, Plus } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Container } from "@/components/layout/container";
import { LinkSegmented } from "@/components/ui/link-segmented";
import { PageHeader } from "@/components/layout/page-header";
import { SummaryTiles } from "@/components/ui/summary-tiles";
import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";

import { STATUS_TONE } from "./status";
import { EmptyState } from "@/components/empty-state";

const PAGE_SIZE = 50;
const MAX_SHOWN = 1000;
const CHUNK = 200; // the API's largest page
const FILTERS = ["all", "draft", "sent", "accepted", "declined", "expired"] as const;

/** Quotes (#44): newest first, by status. */
export default async function QuotesPage({ searchParams }: PageProps<"/quotes">) {
  const t = await getTranslations("quotes");
  const tc = await getTranslations("common");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("clients.read");
  const raw = (await searchParams).status;
  const filter = FILTERS.find((f) => f === raw) ?? "all";
  // The tiles count every quote (a summary query); the list is one status, a page at a time.
  const summary = unwrap(await api.GET("/quotes/summary", { params: scope }));
  const shown = Math.min(MAX_SHOWN, Math.max(PAGE_SIZE, Number((await searchParams).shown) || PAGE_SIZE));
  // One more than shown tells whether a next page exists.
  const quotes: components["schemas"]["QuoteSummary"][] = [];
  while (quotes.length <= shown) {
    const take = Math.min(CHUNK, shown + 1 - quotes.length);
    const chunk = unwrap(
      await api.GET("/quotes", {
        params: { ...scope, query: { status: filter === "all" ? undefined : filter, limit: take, offset: quotes.length } },
      }),
    );
    quotes.push(...chunk);
    if (chunk.length < take) break;
  }
  const hasMore = quotes.length > shown;
  const visibleQuotes = quotes.slice(0, shown);
  const tiles = (["draft", "sent", "accepted", "declined"] as const).map((status) => {
    const rows = summary.filter((row) => (status === "declined" ? ["declined", "expired"].includes(row.status) : row.status === status));
    const currencies = new Set(rows.map((row) => row.currency));
    const count = rows.reduce((sum, row) => sum + row.count, 0);
    return {
      key: status,
      label: t(`tiles.${status}`),
      value: count,
      hint: count > 0 && currencies.size === 1 ? formatMoney(rows.reduce((sum, row) => sum + row.total, 0), [...currencies][0], locale) : undefined,
      href: `/quotes?status=${status}`,
      active: filter === status,
    };
  });
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tenant.time_zone });
  const canSell = tenant.permissions.includes("sales.manage");

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            <FileSignature aria-hidden="true" className="size-8 shrink-0 text-primary-ink" />
            {t("title")}
          </span>
        }
        description={t("subtitle")}
        actions={
          <>
            <Link href="/events" className="btn-secondary px-4 py-2">{t("eventsLink")}</Link>
            {canSell && (
              <Link href="/quotes/new" className="btn-primary px-4 py-2">
                <Plus aria-hidden="true" className="size-4" /> {t("new")}
              </Link>
            )}
          </>
        }
      />
      <LinkSegmented
        variant="chips"
        label={t("filter")}
        loadingLabel={tc("loading")}
        active={filter}
        options={FILTERS.map((f) => ({ key: f, label: t(`filters.${f}`), href: f === "all" ? "/quotes" : `/quotes?status=${f}` }))}
      />
      <SummaryTiles label={t("tiles.label")} tiles={tiles} />
      {visibleQuotes.length === 0 ? (
        <EmptyState variant="list">{t("none")}</EmptyState>
      ) : (
        <ul className="flex flex-col divide-y divide-border card">
          {visibleQuotes.map((quote) => (
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
    </Container>
  );
}
