import { DataTable } from "@/components/ui/data-table";
import type { Metadata } from "next";
import { BRAND } from "@business-os/i18n/brand";
import { getLocale, getTranslations } from "next-intl/server";

import { ColumnChart } from "@/components/charts/column-chart";
import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { getPlatformFor } from "@/lib/platform";
import { StatTile } from "@/components/ui/stat-tile";

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
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                { label: t("mrr"), value: formatMoney(row.mrr, row.currency, locale), note: t("mrrMonth", { month: monthLabel(row.mrr_month) }) },
                { label: t("arr"), value: formatMoney(row.arr, row.currency, locale), note: t("arrNote") },
                { label: t("arpu"), value: formatMoney(row.arpu, row.currency, locale), note: t("arpuNote") },
              ].map((fact) => (
                <StatTile key={fact.label} label={fact.label} value={<span dir="ltr">{fact.value}</span>} hint={fact.note} />
              ))}
            </div>
            <div className="card flex flex-col gap-3 p-4">
              <ColumnChart
                title={t("chart", { currency: row.currency })}
                unit={{ kind: "money", currency: row.currency }}
                tableLabel={tRoot("dashboard.showTable")}
                headers={[t("month"), t("billed")]}
                columns={row.months.map((m) => ({ key: m.month, label: monthLabel(m.month), value: m.billed, display: formatMoney(m.billed, row.currency, locale) }))}
              />
            </div>
            <DataTable
              labelledBy={`metrics-${row.currency}`}
              rows={[...row.months].reverse()}
              rowKey={(m) => m.month}
              columns={[
                { key: "month", header: t("month"), rowHeader: true, cell: (m) => monthLabel(m.month) },
                { key: "invoices", header: t("invoices"), align: "end", className: "tabular-nums", cell: (m) => m.invoices },
                { key: "paid", header: t("paid"), align: "end", className: "tabular-nums", cell: (m) => formatMoney(m.paid, row.currency, locale) },
                { key: "open", header: t("open"), align: "end", className: "tabular-nums", cell: (m) => formatMoney(m.open, row.currency, locale) },
                { key: "billed", header: t("billed"), align: "end", className: "tabular-nums font-medium", cell: (m) => formatMoney(m.billed, row.currency, locale) },
              ]}
            />
          </section>
        ))
      )}

      <section aria-labelledby="metrics-churn" className="flex flex-col gap-3">
        <h2 id="metrics-churn" className="text-lg font-semibold">{t("churn")}</h2>
        {board.churn ? (
          <div className="grid gap-3 sm:grid-cols-3">
            <StatTile label={t("churnRate", { month: monthLabel(board.churn.month) })} value={<span dir="ltr">{board.churn.rate === null ? "-" : percent.format(board.churn.rate)}</span>} />
            <StatTile label={t("cancelled")} value={<span dir="ltr">{board.churn.cancelled}</span>} />
            <StatTile label={t("paying")} value={<span dir="ltr">{board.churn.paying_at_start}</span>} />
          </div>
        ) : (
          <EmptyState variant="list">{t("empty")}</EmptyState>
        )}
      </section>

      {board.ai ? (
        <section aria-labelledby="metrics-ai" className="flex flex-col gap-3">
          <h2 id="metrics-ai" className="text-lg font-semibold">{t("ai")}</h2>
          <p className="text-sm text-muted">{t("aiHint", { days: board.ai.days })}</p>
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { label: t("aiRevenue"), value: board.ai.revenue_usd_minor },
              { label: t("aiCost"), value: board.ai.cost_usd_minor },
              { label: t("aiMargin"), value: board.ai.margin_usd_minor },
            ].map((fact) => (
              <StatTile key={fact.label} label={fact.label} value={<span className={fact.value < 0 ? "text-danger" : undefined} dir="ltr">{formatMoney(fact.value, "USD", locale)}</span>} />
            ))}
          </div>
        </section>
      ) : null}
    </Container>
  );
}
