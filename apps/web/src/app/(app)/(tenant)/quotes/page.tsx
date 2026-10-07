import { FileSignature, Plus } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";

import { STATUS_TONE } from "./status";

const FILTERS = ["all", "draft", "sent", "accepted", "declined", "expired"] as const;

/** Quotes (#44): newest first, by status. */
export default async function QuotesPage({ searchParams }: PageProps<"/quotes">) {
  const t = await getTranslations("quotes");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("clients.read");
  const raw = (await searchParams).status;
  const filter = FILTERS.find((f) => f === raw) ?? "all";
  const quotes = unwrap(
    await api.GET("/quotes", { params: { ...scope, query: filter === "all" ? {} : { status: filter } } }),
  );
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tenant.time_zone });
  const canSell = tenant.permissions.includes("sales.manage");

  return (
    <main className="enter mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="flex items-center gap-2 text-3xl font-bold">
            <FileSignature aria-hidden="true" className="size-7 text-primary" />
            {t("title")}
          </h1>
          <p className="text-sm text-muted">{t("subtitle")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/events" className="btn-secondary px-4 py-2">{t("eventsLink")}</Link>
          {canSell && (
            <Link href="/quotes/new" className="btn-primary px-4 py-2">
              <Plus aria-hidden="true" className="size-4" /> {t("new")}
            </Link>
          )}
        </div>
      </div>
      <nav aria-label={t("filter")} className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <Link
            key={f}
            href={f === "all" ? "/quotes" : `/quotes?status=${f}`}
            aria-current={f === filter ? "page" : undefined}
            className={`rounded-full border px-3 py-1 text-sm ${f === filter ? "border-primary bg-primary text-on-primary" : "border-border bg-surface"}`}
          >
            {t(`filters.${f}`)}
          </Link>
        ))}
      </nav>
      {quotes.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("none")}</p>
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
    </main>
  );
}
