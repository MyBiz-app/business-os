import type { components } from "@business-os/api-client";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { ColumnChart } from "@/components/charts/column-chart";
import { isolate } from "@/lib/bidi";
import { formatDay } from "@/lib/dates";

type Insights = components["schemas"]["Insights"];

const SOURCES = ["direct", "search", "social", "other"] as const;

/** A live site's last 30 days: visits per day and where they came from, and the enquiries that
 * came through its contact form. */
export async function InsightsPanel({ insights }: { insights: Insights }) {
  const t = await getTranslations("website.insights");
  const locale = await getLocale();
  const number = new Intl.NumberFormat(locale);
  const label = (day: string) => formatDay(day, locale, { day: "numeric", month: "numeric" });
  return (
    <section className="card flex flex-col gap-6 p-6" aria-labelledby="site-insights">
      <h2 id="site-insights" className="text-lg font-semibold">{t("title")}</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs font-medium text-muted">{t("visits")}</p>
          <p className="text-3xl font-bold tabular-nums">{number.format(insights.visits_total)}</p>
        </div>
        <Link href="/leads?source=form" className="rounded-xl border border-border bg-surface p-4 transition-colors hover:border-primary">
          <p className="text-xs font-medium text-muted">{t("enquiries")}</p>
          <p className="text-3xl font-bold tabular-nums">{number.format(insights.enquiries_total)}</p>
        </Link>
      </div>
      {insights.visits_total === 0 ? (
        <p className="text-sm text-muted">{t("noVisits")}</p>
      ) : (
        <>
          <ColumnChart
            title={t("perDay")}
            unit={{ kind: "count" }}
            tableLabel={t("showTable")}
            headers={[t("day"), t("visits")]}
            columns={insights.days.map((point) => ({ key: point.day, label: label(point.day), value: point.visits, display: number.format(point.visits) }))}
          />
          <div className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold">{t("sources")}</h3>
            <ul className="flex flex-wrap gap-2 text-sm">
              {SOURCES.map((source) => (
                <li key={source} className="rounded-full border border-border px-3 py-1">
                  {t(`source.${source}`)} <span className="font-semibold tabular-nums">{number.format(insights.sources[source] ?? 0)}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold">{t("latest")}</h3>
        {insights.enquiries.length === 0 ? (
          <p className="text-sm text-muted">{t("noEnquiries")}</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {insights.enquiries.map((enquiry) => (
              <li key={enquiry.id}>
                <Link href={`/leads/${enquiry.id}`} className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-sm hover:bg-background">
                  <span dir="auto" className="truncate font-medium">{isolate(enquiry.name)}</span>
                  <span className="shrink-0 text-xs text-muted">{formatDay(enquiry.created_at.slice(0, 10), locale, { day: "numeric", month: "long" })}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
