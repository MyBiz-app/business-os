import { getLocale, getTranslations } from "next-intl/server";

import { DataTable } from "@/components/ui/data-table";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { unwrap } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { formatMoney } from "@/lib/money";
import { getPlatformFor } from "@/lib/platform";

type Comparison = {
  item: string;
  currency: string;
  ours_minor: number;
  cheapest_minor: number;
  cheapest_competitor: string;
  gap_percent: number;
  pricier: boolean;
};
type PriceRow = { item: string; competitor: string; currency: string; price_minor: number; source_url: string; checked_on: string };

/** The saved market reports: our price against the cheapest competitor, dearer items in red,
 * and every price with its source link and the date it was read. */
export async function MarketReports() {
  const t = await getTranslations("platform.ai.reports");
  const locale = await getLocale();
  const { api } = await getPlatformFor("usage.read");
  const list = unwrap(await api.GET("/platform/ai/reports", { params: { query: { kind: "market", limit: 10 } } }));
  const reports = await Promise.all(
    list.map(async (r) => unwrap(await api.GET("/platform/ai/reports/{report_id}", { params: { path: { report_id: r.id } } }))),
  );
  const stamp = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const percent = new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 1 });

  if (reports.length === 0) return <p className="card p-4 sm:p-5 text-sm text-muted">{t("empty")}</p>;
  return (
    <div className="flex flex-col gap-3">
      {reports.map((report) => {
        const comparison = (report.body.comparison ?? []) as Comparison[];
        const prices = (report.body.prices ?? []) as PriceRow[];
        const dearer = comparison.filter((c) => c.pricier).length;
        return (
          <CollapsibleSection
            key={report.id}
            storageKey={`ai-report-${report.id}`}
            title={
              <span dir="auto">
                {report.title}
                {dearer > 0 && <span className="ms-2 rounded-full bg-danger/10 px-2 py-0.5 text-xs text-danger">{t("dearer", { count: dearer })}</span>}
              </span>
            }
            description={`${stamp.format(new Date(report.created_at))} - ${t("by")} ${report.created_by}`}
          >
            <div className="flex flex-col gap-4">
              <p className="text-sm" dir="auto">{report.summary}</p>
              <DataTable
                labelledBy={`report-${report.id}`}
                bare
                className="rounded-xl border border-border"
                rows={comparison}
                rowKey={(c) => `${c.item}-${c.currency}`}
                density="compact"
                rowClassName={(c) => (c.pricier ? "bg-danger/10" : undefined)}
                columns={[
                  { key: "item", header: t("item"), cell: (c) => <bdi>{c.item}</bdi> },
                  { key: "ours", header: t("ours"), align: "end", className: "tabular-nums", cell: (c) => <bdi>{formatMoney(c.ours_minor, c.currency, locale)}</bdi> },
                  { key: "cheapest", header: t("cheapest"), align: "end", className: "tabular-nums", cell: (c) => <bdi>{formatMoney(c.cheapest_minor, c.currency, locale)}</bdi> },
                  { key: "competitor", header: t("competitor"), cell: (c) => <span dir="auto">{c.cheapest_competitor}</span> },
                  {
                    key: "gap",
                    header: t("gap"),
                    align: "end",
                    className: "tabular-nums",
                    cell: (c) => (
                      <span className={c.pricier ? "font-medium text-danger" : undefined}>
                        <bdi>{percent.format(c.gap_percent / 100)}</bdi>
                        {c.pricier && <span className="ms-2 text-xs">{t("pricier")}</span>}
                      </span>
                    ),
                  },
                ]}
              />
              <ul className="flex flex-col gap-1 text-sm">
                {prices.map((p, index) => (
                  <li key={index} className="flex flex-wrap gap-x-3 text-muted">
                    <span dir="auto">{p.competitor}</span>
                    <bdi>{isolate(p.item)}</bdi>
                    <bdi>{formatMoney(p.price_minor, p.currency, locale)}</bdi>
                    <a href={p.source_url} target="_blank" rel="noopener noreferrer" className="underline" dir="ltr">
                      {t("source")}
                    </a>
                    <span>{t("checked")} {p.checked_on}</span>
                  </li>
                ))}
              </ul>
            </div>
          </CollapsibleSection>
        );
      })}
    </div>
  );
}
