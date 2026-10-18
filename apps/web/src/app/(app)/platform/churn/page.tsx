import { getLocale, getTranslations } from "next-intl/server";

import { ColumnChart } from "@/components/charts/column-chart";
import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { ScrollRegion } from "@/components/scroll-region";
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
        <ScrollRegion labelledBy="churn-months" className="card">
          <table className="w-full text-sm">
            <thead className="text-muted">
              <tr className="border-b border-border">
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("churn.month")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("churn.cancelled")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("churn.paused")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("churn.resumed")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("churn.rate")}</th>
              </tr>
            </thead>
            <tbody>
              {[...months].reverse().map((row) => (
                <tr key={row.month} className="border-b border-border last:border-0">
                  <th scope="row" className="px-4 py-3 text-start font-medium">{monthLabel(row.month)}</th>
                  <td className="px-4 py-3 text-end tabular-nums">{row.cancelled}</td>
                  <td className="px-4 py-3 text-end tabular-nums">{row.paused}</td>
                  <td className="px-4 py-3 text-end tabular-nums">{row.resumed}</td>
                  <td className="px-4 py-3 text-end tabular-nums">{row.paying_at_start > 0 ? percent.format(row.cancelled / row.paying_at_start) : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
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
          <ScrollRegion labelledBy="churn-list" className="card">
            <table className="w-full text-sm">
              <thead className="text-muted">
                <tr className="border-b border-border">
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("churn.business")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("churn.outcome")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("churn.when")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("churn.ends")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("churn.reasonsTitle")}</th>
                  <th scope="col" className="px-4 py-3 text-end font-medium">{t("churn.refund")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-b border-border align-top last:border-0">
                    <td className="px-4 py-3">
                      <span className="font-medium">{row.name}</span>
                      {row.owner_email ? <span className="block text-xs text-muted" dir="ltr">{row.owner_email}</span> : null}
                    </td>
                    <td className="px-4 py-3">
                      <Pill tone={row.outcome === "cancelled" ? "danger" : "warning"}>{t(`churn.outcomes.${row.outcome}`)}</Pill>
                      {row.resumed_at ? <span className="ms-2 text-xs text-muted">{t("churn.back")}</span> : null}
                    </td>
                    <td className="px-4 py-3">{formatDay(row.created_at, locale, { day: "numeric", month: "numeric", year: "numeric" })}</td>
                    <td className="px-4 py-3">{row.ends_at ? formatDay(row.ends_at, locale, { day: "numeric", month: "numeric", year: "numeric" }) : "-"}</td>
                    <td className="px-4 py-3">
                      {row.reason ? t(`churn.reasons.${row.reason as (typeof REASONS)[number]}`) : t("churn.noReason")}
                      {row.note ? <span className="block text-xs text-muted">{row.note}</span> : null}
                    </td>
                    <td className="px-4 py-3 text-end tabular-nums">{row.refund_minor ? formatMoney(row.refund_minor, row.currency, locale) : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        )}
      </section>
    </Container>
  );
}
