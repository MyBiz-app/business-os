import type { components } from "@business-os/api-client";
import { getTranslations } from "next-intl/server";

import { branchColor } from "@/lib/calendar";
import { formatMoney } from "@/lib/money";

type BranchMetrics = components["schemas"]["BranchMetrics"];

/** Branches side by side, metric by metric: a bar per branch, scaled to the best of them, with
 * the total (or average, for rates) under each metric. Same definitions as the dashboard. */
export async function BranchComparison({ rows, currency, locale }: { rows: BranchMetrics[]; currency: string; locale: string }) {
  const t = await getTranslations("reports.compare");
  const tMetrics = await getTranslations("metrics");
  const number = new Intl.NumberFormat(locale);
  const keys = rows[0]?.metrics.map((m) => m.key) ?? [];
  const show = (unit: string, value: number | null) =>
    value === null ? "—" : unit === "money" ? formatMoney(Math.round(value), currency, locale) : unit === "percent" ? `${number.format(Math.round(value))}%` : number.format(value);

  return (
    <section aria-labelledby="compare-heading" className="card flex flex-col gap-5 p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 id="compare-heading" className="text-lg font-semibold">
            {t("title")}
          </h2>
          <p className="text-sm text-muted">{t("subtitle")}</p>
        </div>
        <ul className="flex flex-wrap gap-3 text-xs text-muted">
          {rows.map((row, i) => (
            <li key={row.location_id} className="flex items-center gap-1.5">
              <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: branchColor(i) }} />
              <span dir="auto">{row.name}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="grid gap-x-8 gap-y-6 md:grid-cols-2">
        {keys.map((key) => {
          const values = rows.map((row) => row.metrics.find((m) => m.key === key)!);
          const unit = values[0].unit;
          const max = Math.max(0, ...values.map((v) => v.value ?? 0));
          const known = values.filter((v) => v.value !== null).map((v) => v.value as number);
          const summary = unit === "percent" ? (known.length ? known.reduce((a, b) => a + b, 0) / known.length : null) : known.reduce((a, b) => a + b, 0);
          const best = values[0].higher_is_better ? Math.max(...known) : Math.min(...known);
          return (
            <figure key={key} className="flex flex-col gap-2">
              <figcaption className="flex items-baseline justify-between gap-2">
                <span className="text-sm font-semibold">{tMetrics(key as "revenue")}</span>
                <span className="text-xs text-muted">
                  {unit === "percent" ? t("average") : t("total")} <span className="font-semibold text-foreground tabular-nums">{show(unit, summary)}</span>
                </span>
              </figcaption>
              <ul className="flex flex-col gap-1.5">
                {rows.map((row, i) => {
                  const value = values[i].value;
                  return (
                    <li key={row.location_id} className="grid grid-cols-[minmax(5rem,9rem)_1fr_auto] items-center gap-3 text-sm">
                      <span dir="auto" className="truncate text-muted">
                        {row.name}
                      </span>
                      <span aria-hidden="true" className="h-2.5 overflow-hidden rounded-full bg-foreground/6">
                        <span className="block h-full rounded-full" style={{ width: `${max > 0 && value ? (value / max) * 100 : 0}%`, background: branchColor(i) }} />
                      </span>
                      <span className={`tabular-nums ${known.length > 1 && value === best ? "font-semibold" : ""}`}>{show(unit, value)}</span>
                    </li>
                  );
                })}
              </ul>
            </figure>
          );
        })}
      </div>
    </section>
  );
}
