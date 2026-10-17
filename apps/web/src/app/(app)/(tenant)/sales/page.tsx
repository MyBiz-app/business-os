import { ChevronLeft, ChevronRight, Download, Receipt, X } from "lucide-react";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Ltr } from "@/components/bidi";
import { PendingArea, PeriodPicker, PeriodProvider } from "@/components/period-picker";
import { ScrollRegion } from "@/components/scroll-region";
import { unwrap } from "@/lib/api";
import { formatDay, todayIn } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { resolveRange } from "@/lib/range";
import { getTenantFor } from "@/lib/tenant";

import { monthRange } from "./month";
import { EmptyState } from "@/components/empty-state";

const PRESETS = [7, 30, 90] as const;

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("sales");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** A month of sales: the total, the split by payment method and every receipt. */
export default async function SalesPage({ searchParams }: PageProps<"/sales">) {
  const t = await getTranslations("sales");
  const tReceipts = await getTranslations("receipts");
  const tPeriod = await getTranslations("period");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("reports.read");
  const query = await searchParams;
  const today = todayIn(tenant.time_zone);
  // A free range (`?from=&to=` or `?period=30`) replaces the calendar month.
  const free = query.from || query.to || query.period ? resolveRange(query, today, { presets: PRESETS, fallback: 30, includeToday: true }) : null;
  const months = monthRange(query.month, tenant.time_zone);
  const { month, previous, next } = months;
  const start = free?.start ?? months.start;
  const end = free?.end ?? months.end;
  const exportQuery = free ? new URLSearchParams({ from: start, to: end }) : new URLSearchParams({ month });
  const sales = unwrap(await api.GET("/sales", { params: { ...scope, query: { start, end } } }));
  // One payment method only, from a click on its bar.
  const method = sales.by_method.find((m) => m.method === query.method)?.method;
  const receipts = method ? sales.receipts.filter((r) => r.method === method) : sales.receipts;
  const linkTo = (extra: Record<string, string>) => {
    const link = new URLSearchParams(free ? { from: start, to: end } : { month });
    for (const [key, value] of Object.entries(extra)) link.set(key, value);
    return `/sales?${link}`;
  };
  const money = (amount: number) => formatMoney(amount, sales.currency, locale);
  const title = free
    ? `${formatDay(start, locale, { day: "numeric", month: "short", year: "numeric" })} - ${formatDay(end, locale, { day: "numeric", month: "short", year: "numeric" })}`
    : new Date(`${start}T12:00:00Z`).toLocaleDateString(locale, { month: "long", year: "numeric", timeZone: "UTC" });
  const day = (instant: string) =>
    new Date(instant).toLocaleDateString(locale, { day: "numeric", month: "short", timeZone: tenant.time_zone });

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader
        title={t("title")}
        description={t("subtitle")}
        actions={
          <>
            <Link href="/sales/orders" className="btn-secondary px-4 py-2 text-sm">
              {t("orders.link")}
            </Link>
            <a href={`/sales/export?${exportQuery}`} className="btn-secondary px-4 py-2 text-sm" download>
              <Download aria-hidden="true" className="size-4" />
              {t("export")}
            </a>
          </>
        }
      />

      <PeriodProvider>
      <div className="flex flex-wrap items-center justify-between gap-3 card px-4 py-3">
        {free ? (
          <p className="text-lg font-semibold">{title}</p>
        ) : (
          <nav aria-label={title} className="flex flex-1 items-center justify-between gap-3 sm:justify-start sm:gap-4">
            <Link scroll={false} href={`/sales?month=${previous}`} aria-label={t("previous")} className="flex size-9 items-center justify-center rounded-lg hover:bg-foreground/5">
              <ChevronRight aria-hidden="true" className="size-5 ltr:rotate-180" />
            </Link>
            <p className="text-lg font-semibold">{title}</p>
            <Link scroll={false} href={`/sales?month=${next}`} aria-label={t("next")} className="flex size-9 items-center justify-center rounded-lg hover:bg-foreground/5">
              <ChevronLeft aria-hidden="true" className="size-5 ltr:rotate-180" />
            </Link>
          </nav>
        )}
        <PeriodPicker
          presets={PRESETS}
          value={free?.key ?? "month"}
          from={start}
          to={end}
          today={today}
          extra={[{ value: "month", label: tPeriod("month") }]}
          reset={["month", "method"]}
        />
      </div>
      <PendingArea className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-[1fr_2fr]">
        <Link href={`${linkTo({})}#receipts-heading`} className="contents">
        <section aria-labelledby="total-heading" className="card-accent card-hover flex flex-col gap-2 p-6">
          <h2 id="total-heading" className="text-sm font-medium text-muted">
            {t("total")}
          </h2>
          <p className="text-4xl font-extrabold tracking-tight">
            <bdi>{money(sales.total)}</bdi>
          </p>
          <p className="text-sm text-muted">{t("count", { count: sales.count })}</p>
        </section>
        </Link>
        <section aria-labelledby="methods-heading" className="card flex flex-col gap-3 p-6">
          <h2 id="methods-heading" className="text-sm font-medium text-muted">
            {t("byMethod")}
          </h2>
          {sales.by_method.length === 0 ? (
            <p className="text-sm text-muted">{t("empty")}</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {sales.by_method.map((m) => (
                <li key={m.method}>
                  <Link
                    href={`${linkTo({ method: m.method })}#receipts-heading`}
                    aria-current={method === m.method ? "true" : undefined}
                    className="flex flex-col gap-1 rounded-lg px-1 py-0.5 transition-colors hover:bg-foreground/5"
                  >
                  <span className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="font-medium">
                      {tReceipts(`methods.${m.method}`)} <span className="text-muted">· {m.count}</span>
                    </span>
                    <bdi className="font-semibold">{money(m.amount)}</bdi>
                  </span>
                  <span aria-hidden="true" className="h-2 overflow-hidden rounded-full bg-foreground/8">
                    <span className="block h-full rounded-full bg-primary" style={{ width: `${sales.total ? (m.amount / sales.total) * 100 : 0}%` }} />
                  </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section aria-labelledby="receipts-heading" className="flex flex-col gap-3">
        <h2 id="receipts-heading" className="flex items-center gap-2 text-lg font-semibold">
          <Receipt aria-hidden="true" className="size-5 text-primary-ink" />
          {t("receipts")}
        </h2>
        {sales.simulated && <p className="rounded-xl bg-warning/10 px-3 py-2 text-sm">{t("simulated")}</p>}
        {method && (
          <Link
            href={linkTo({})}
            scroll={false}
            className="inline-flex w-fit items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary-ink transition-colors hover:bg-primary/15"
          >
            {tReceipts(`methods.${method}`)}
            <X aria-hidden="true" className="size-3.5" />
            <span className="sr-only">{t("removeFilter")}</span>
          </Link>
        )}
        {receipts.length === 0 ? (
          <EmptyState variant="chart">{t("empty")}</EmptyState>
        ) : (
          <ScrollRegion labelledBy="receipts-heading" className="rounded-2xl border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("number")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("date")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("client")}</th>
                  <th scope="col" className="hidden px-4 py-3 text-start font-medium md:table-cell">{t("item")}</th>
                  <th scope="col" className="hidden px-4 py-3 text-start font-medium sm:table-cell">{t("method")}</th>
                  <th scope="col" className="px-4 py-3 text-end font-medium">{t("amount")}</th>
                </tr>
              </thead>
              <tbody>
                {receipts.map((r) => (
                  <tr key={r.id} className="border-t border-border transition-colors hover:bg-primary/4">
                    <td className="px-4 py-2.5">
                      <Link href={`/receipts/${r.id}`} className="font-medium text-primary-ink underline-offset-4 hover:underline">
                        <Ltr>{r.number}</Ltr>
                      </Link>
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5">{day(r.issued_at)}</td>
                    <td className="px-4 py-2.5" dir="auto">
                      <Link href={`/clients/${r.client_id}`} className="underline-offset-4 hover:underline">
                        {r.client_name}
                      </Link>
                    </td>
                    <td className="hidden px-4 py-2.5 md:table-cell" dir="auto">{r.description}</td>
                    <td className="hidden px-4 py-2.5 sm:table-cell">{tReceipts(`methods.${r.method}`)}</td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-end font-semibold">
                      <bdi>{money(r.amount)}</bdi>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        )}
      </section>
      </PendingArea>
      </PeriodProvider>
    </Container>
  );
}
