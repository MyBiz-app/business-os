import { DataTable } from "@/components/ui/data-table";
import { getLocale, getTranslations } from "next-intl/server";

import { ColumnChart } from "@/components/charts/column-chart";
import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { getPlatformFor } from "@/lib/platform";

const REASONS = ["too_expensive", "missing_feature", "not_using", "switched", "other"] as const;

/** Who cancelled or paused their MyBiz subscription, why, and how it moves month to month (R33). */
export default async function ChurnPage() {
  const t = await getTranslations("platform");
  const tRoot = await getTranslations();
  const locale = await getLocale();
  const { api } = await getPlatformFor("billing.manage");
  const months = unwrap(await api.GET("/platform/billing/churn"));
  const rows = unwrap(await api.GET("/platform/billing/cancellations"));
  const percent = new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 1 });
  const cancelled = rows.filter((row) => row.outcome === "cancelled");
  const reasonCounts = [...REASONS, null].map((reason) => ({ reason, count: cancelled.filter((row) => (row.reason ?? null) === reason).length }));
  const monthLabel = (value: string) => formatDay(value, locale, { month: "short", year: "2-digit" });

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("churn.title")} description={t("churn.hint")} />

      <section aria-labelledby="churn-chart" className="card flex flex-col gap-3 p-4">
        <h2 id="churn-chart" className="sr-only">{t("churn.chart")}</h2>
        <ColumnChart
          title={t("churn.chart")}
          unit={{ kind: "count" }}
          tableLabel={tRoot("dashboard.showTable")}
          headers={[t("churn.month"), t("churn.cancelled")]}
          columns={months.map((row) => ({ key: row.month, label: monthLabel(row.month), value: row.cancelled, display: String(row.cancelled) }))}
        />
      </section>

      <section aria-labelledby="churn-months" className="flex flex-col gap-3">
        <h2 id="churn-months" className="text-lg font-semibold">{t("churn.rate")}</h2>
        <DataTable
          labelledBy="churn-months"
          rows={[...months].reverse()}
          rowKey={(row) => row.month}
          columns={[
            { key: "month", header: t("churn.month"), rowHeader: true, cell: (row) => monthLabel(row.month) },
            { key: "cancelled", header: t("churn.cancelled"), align: "end", className: "tabular-nums", cell: (row) => row.cancelled },
            { key: "paused", header: t("churn.paused"), align: "end", className: "tabular-nums", cell: (row) => row.paused },
            { key: "resumed", header: t("churn.resumed"), align: "end", className: "tabular-nums", cell: (row) => row.resumed },
            {
              key: "rate",
              header: t("churn.rate"),
              align: "end",
              className: "tabular-nums",
              cell: (row) => (row.paying_at_start > 0 ? percent.format(row.cancelled / row.paying_at_start) : "-"),
            },
          ]}
        />
      </section>

      <section aria-labelledby="churn-reasons" className="flex flex-col gap-3">
        <h2 id="churn-reasons" className="text-lg font-semibold">{t("churn.reasonsTitle")}</h2>
        <ul className="card flex flex-col divide-y divide-border">
          {reasonCounts.map(({ reason, count }) => (
            <li key={reason ?? "none"} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
              <span>{reason ? t(`churn.reasons.${reason}`) : t("churn.noReason")}</span>
              <span className="tabular-nums font-medium">{count}</span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="churn-list" className="flex flex-col gap-3">
        <h2 id="churn-list" className="text-lg font-semibold">{t("churn.listTitle")}</h2>
        {rows.length === 0 ? (
          <EmptyState variant="list">{t("churn.empty")}</EmptyState>
        ) : (
          <DataTable
            labelledBy="churn-list"
            rows={rows}
            rowKey={(row) => row.id}
            rowClassName={() => "align-top"}
            columns={[
              {
                key: "business",
                header: t("churn.business"),
                cell: (row) => (
                  <>
                    <span className="font-medium">{row.name}</span>
                    {row.owner_email ? <span className="block text-xs text-muted" dir="ltr">{row.owner_email}</span> : null}
                  </>
                ),
              },
              {
                key: "outcome",
                header: t("churn.outcome"),
                cell: (row) => (
                  <>
                    <Pill tone={row.outcome === "cancelled" ? "danger" : "warning"}>{t(`churn.outcomes.${row.outcome}`)}</Pill>
                    {row.resumed_at ? <span className="ms-2 text-xs text-muted">{t("churn.back")}</span> : null}
                  </>
                ),
              },
              { key: "when", header: t("churn.when"), cell: (row) => formatDay(row.created_at, locale, { day: "numeric", month: "numeric", year: "numeric" }) },
              {
                key: "ends",
                header: t("churn.ends"),
                cell: (row) => (row.ends_at ? formatDay(row.ends_at, locale, { day: "numeric", month: "numeric", year: "numeric" }) : "-"),
              },
              {
                key: "reason",
                header: t("churn.reasonsTitle"),
                cell: (row) => (
                  <>
                    {row.reason ? t(`churn.reasons.${row.reason as (typeof REASONS)[number]}`) : t("churn.noReason")}
                    {row.note ? <span className="block text-xs text-muted">{row.note}</span> : null}
                  </>
                ),
              },
              {
                key: "refund",
                header: t("churn.refund"),
                align: "end",
                className: "tabular-nums",
                cell: (row) => (row.refund_minor ? formatMoney(row.refund_minor, row.currency, locale) : "-"),
              },
            ]}
          />
        )}
      </section>
    </Container>
  );
}
