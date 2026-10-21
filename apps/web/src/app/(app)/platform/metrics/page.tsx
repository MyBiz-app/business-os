import type { Metadata } from "next";
import { BRAND } from "@business-os/i18n/brand";
import { getLocale, getTranslations } from "next-intl/server";

import { ColumnChart } from "@/components/charts/column-chart";
import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { ScrollRegion } from "@/components/scroll-region";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { getPlatformFor } from "@/lib/platform";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("platform.metrics");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** SaaS numbers (K3): recurring revenue, churn, revenue per business and the AI margin. */
export default async function PlatformMetricsPage() {
  const t = await getTranslations("platform.metrics");
  const tRoot = await getTranslations();
  const locale = await getLocale();
  const { api } = await getPlatformFor("billing.manage");
  const board = unwrap(await api.GET("/platform/metrics/saas"));
  const percent = new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 1 });
  const monthLabel = (value: string) => formatDay(value, locale, { month: "short", year: "2-digit" });

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-8 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("hint")} />

      {board.currencies.length === 0 ? (
        <EmptyState variant="list">{t("empty")}</EmptyState>
      ) : (
        board.currencies.map((row) => (
          <section key={row.currency} aria-labelledby={`metrics-${row.currency}`} className="flex flex-col gap-4">
            <h2 id={`metrics-${row.currency}`} className="text-lg font-semibold">{t("currency", { currency: row.currency })}</h2>
            <dl className="grid gap-3 sm:grid-cols-3">
              {[
                { label: t("mrr"), value: formatMoney(row.mrr, row.currency, locale), note: t("mrrMonth", { month: monthLabel(row.mrr_month) }) },
                { label: t("arr"), value: formatMoney(row.arr, row.currency, locale), note: t("arrNote") },
                { label: t("arpu"), value: formatMoney(row.arpu, row.currency, locale), note: t("arpuNote") },
              ].map((fact) => (
                <div key={fact.label} className="card flex flex-col gap-1 p-5">
                  <dt className="text-sm text-muted">{fact.label}</dt>
                  <dd className="text-2xl font-semibold" dir="ltr">{fact.value}</dd>
                  <dd className="text-xs text-muted">{fact.note}</dd>
                </div>
              ))}
            </dl>
            <div className="card flex flex-col gap-3 p-4">
              <ColumnChart
                title={t("chart", { currency: row.currency })}
                unit={{ kind: "money", currency: row.currency }}
                tableLabel={tRoot("dashboard.showTable")}
                headers={[t("month"), t("billed")]}
                columns={row.months.map((m) => ({ key: m.month, label: monthLabel(m.month), value: m.billed, display: formatMoney(m.billed, row.currency, locale) }))}
              />
            </div>
            <ScrollRegion labelledBy={`metrics-${row.currency}`} className="card">
              <table className="w-full text-sm">
                <thead className="text-muted">
                  <tr className="border-b border-border">
                    <th scope="col" className="px-4 py-3 text-start font-medium">{t("month")}</th>
                    <th scope="col" className="px-4 py-3 text-end font-medium">{t("invoices")}</th>
                    <th scope="col" className="px-4 py-3 text-end font-medium">{t("paid")}</th>
                    <th scope="col" className="px-4 py-3 text-end font-medium">{t("open")}</th>
                    <th scope="col" className="px-4 py-3 text-end font-medium">{t("billed")}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...row.months].reverse().map((m) => (
                    <tr key={m.month} className="border-b border-border last:border-0">
                      <th scope="row" className="px-4 py-3 text-start font-medium">{monthLabel(m.month)}</th>
                      <td className="px-4 py-3 text-end tabular-nums">{m.invoices}</td>
                      <td className="px-4 py-3 text-end tabular-nums">{formatMoney(m.paid, row.currency, locale)}</td>
                      <td className="px-4 py-3 text-end tabular-nums">{formatMoney(m.open, row.currency, locale)}</td>
                      <td className="px-4 py-3 text-end tabular-nums font-medium">{formatMoney(m.billed, row.currency, locale)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
          </section>
        ))
      )}

      <section aria-labelledby="metrics-churn" className="flex flex-col gap-3">
        <h2 id="metrics-churn" className="text-lg font-semibold">{t("churn")}</h2>
        {board.churn ? (
          <dl className="grid gap-3 sm:grid-cols-3">
            <div className="card flex flex-col gap-1 p-5">
              <dt className="text-sm text-muted">{t("churnRate", { month: monthLabel(board.churn.month) })}</dt>
              <dd className="text-2xl font-semibold" dir="ltr">{board.churn.rate === null ? "-" : percent.format(board.churn.rate)}</dd>
            </div>
            <div className="card flex flex-col gap-1 p-5">
              <dt className="text-sm text-muted">{t("cancelled")}</dt>
              <dd className="text-2xl font-semibold" dir="ltr">{board.churn.cancelled}</dd>
            </div>
            <div className="card flex flex-col gap-1 p-5">
              <dt className="text-sm text-muted">{t("paying")}</dt>
              <dd className="text-2xl font-semibold" dir="ltr">{board.churn.paying_at_start}</dd>
            </div>
          </dl>
        ) : (
          <EmptyState variant="list">{t("empty")}</EmptyState>
        )}
      </section>

      {board.ai ? (
        <section aria-labelledby="metrics-ai" className="flex flex-col gap-3">
          <h2 id="metrics-ai" className="text-lg font-semibold">{t("ai")}</h2>
          <p className="text-sm text-muted">{t("aiHint", { days: board.ai.days })}</p>
          <dl className="grid gap-3 sm:grid-cols-3">
            {[
              { label: t("aiRevenue"), value: board.ai.revenue_usd_minor },
              { label: t("aiCost"), value: board.ai.cost_usd_minor },
              { label: t("aiMargin"), value: board.ai.margin_usd_minor },
            ].map((fact) => (
              <div key={fact.label} className="card flex flex-col gap-1 p-5">
                <dt className="text-sm text-muted">{fact.label}</dt>
                <dd className={`text-2xl font-semibold ${fact.value < 0 ? "text-danger" : ""}`} dir="ltr">{formatMoney(fact.value, "USD", locale)}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
    </Container>
  );
}
