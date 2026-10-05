import { ChevronLeft, ChevronRight, Download, Receipt } from "lucide-react";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { ScrollRegion } from "@/components/scroll-region";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";

import { monthRange } from "./month";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("sales");
  return { title: `${t("title")} · MyBiz` };
}

/** A month of sales: the total, the split by payment method and every receipt. */
export default async function SalesPage({ searchParams }: PageProps<"/sales">) {
  const t = await getTranslations("sales");
  const tReceipts = await getTranslations("receipts");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("reports.read");
  const { month, start, end, previous, next } = monthRange((await searchParams).month, tenant.time_zone);
  const sales = unwrap(await api.GET("/sales", { params: { ...scope, query: { start, end } } }));
  const money = (amount: number) => formatMoney(amount, sales.currency, locale);
  const title = new Date(`${start}T12:00:00Z`).toLocaleDateString(locale, { month: "long", year: "numeric", timeZone: "UTC" });
  const day = (instant: string) =>
    new Date(instant).toLocaleDateString(locale, { day: "numeric", month: "short", timeZone: tenant.time_zone });

  return (
    <main className="enter mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <p className="text-muted">{t("subtitle")}</p>
        </div>
        <a href={`/sales/export?month=${month}`} className="btn-secondary px-4 py-2 text-sm" download>
          <Download aria-hidden="true" className="size-4" />
          {t("export")}
        </a>
      </div>

      <nav aria-label={title} className="flex items-center justify-between gap-3 card px-4 py-3">
        <Link href={`/sales?month=${previous}`} aria-label={t("previous")} className="flex size-9 items-center justify-center rounded-lg hover:bg-foreground/5">
          <ChevronRight aria-hidden="true" className="size-5 ltr:rotate-180" />
        </Link>
        <p className="text-lg font-semibold">{title}</p>
        <Link href={`/sales?month=${next}`} aria-label={t("next")} className="flex size-9 items-center justify-center rounded-lg hover:bg-foreground/5">
          <ChevronLeft aria-hidden="true" className="size-5 ltr:rotate-180" />
        </Link>
      </nav>

      <div className="grid gap-4 md:grid-cols-[1fr_2fr]">
        <section aria-labelledby="total-heading" className="card-accent flex flex-col gap-2 p-6">
          <h2 id="total-heading" className="text-sm font-medium text-muted">
            {t("total")}
          </h2>
          <p className="text-4xl font-extrabold tracking-tight">
            <bdi>{money(sales.total)}</bdi>
          </p>
          <p className="text-sm text-muted">{t("count", { count: sales.count })}</p>
        </section>
        <section aria-labelledby="methods-heading" className="card flex flex-col gap-3 p-6">
          <h2 id="methods-heading" className="text-sm font-medium text-muted">
            {t("byMethod")}
          </h2>
          {sales.by_method.length === 0 ? (
            <p className="text-sm text-muted">{t("empty")}</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {sales.by_method.map((m) => (
                <li key={m.method} className="flex flex-col gap-1">
                  <span className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="font-medium">
                      {tReceipts(`methods.${m.method}`)} <span className="text-muted">· {m.count}</span>
                    </span>
                    <bdi className="font-semibold">{money(m.amount)}</bdi>
                  </span>
                  <span aria-hidden="true" className="h-2 overflow-hidden rounded-full bg-foreground/8">
                    <span className="block h-full rounded-full bg-primary" style={{ width: `${sales.total ? (m.amount / sales.total) * 100 : 0}%` }} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section aria-labelledby="receipts-heading" className="flex flex-col gap-3">
        <h2 id="receipts-heading" className="flex items-center gap-2 text-lg font-semibold">
          <Receipt aria-hidden="true" className="size-5 text-primary" />
          {t("receipts")}
        </h2>
        {sales.simulated && <p className="rounded-xl bg-warning/10 px-3 py-2 text-sm">{t("simulated")}</p>}
        {sales.receipts.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("empty")}</p>
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
                {sales.receipts.map((r) => (
                  <tr key={r.id} className="border-t border-border transition-colors hover:bg-primary/4">
                    <td className="px-4 py-2.5">
                      <Link href={`/receipts/${r.id}`} className="font-medium text-primary underline-offset-4 hover:underline">
                        {r.number}
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
    </main>
  );
}
