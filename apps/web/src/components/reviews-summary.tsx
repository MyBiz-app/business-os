import type { components } from "@business-os/api-client";
import { Star } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

type Summary = components["schemas"]["ReviewSummary"];

/** Five stars, filled up to the rating; the number is given in text for screen readers. */
export function Stars({ rating, label }: { rating: number; label: string }) {
  return (
    <span role="img" aria-label={label} className="inline-flex shrink-0 gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          aria-hidden="true"
          className={`size-4 ${n <= Math.round(rating) ? "fill-amber-400 text-amber-500" : "text-foreground/20"}`}
        />
      ))}
    </span>
  );
}

type Props = {
  summary: Summary;
  locale: string;
  timeZone: string;
  title: string;
  /** Show who wrote each review (the business's view); off on a client's own page. */
  withClients?: boolean;
  /** Show the per-staff and per-service averages. */
  withGroups?: boolean;
};

export async function ReviewsSummary({ summary, locale, timeZone, title, withClients = true, withGroups = true }: Props) {
  const t = await getTranslations("reviews");
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
  const when = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone });
  const most = Math.max(1, ...summary.distribution);
  const starsLabel = (rating: number) => t("starsLabel", { rating: number.format(rating) });

  const group = (heading: string, rows: Summary["by_staff"]) =>
    rows.length > 0 && (
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold">{heading}</h3>
        <ul className="flex flex-col divide-y divide-border text-sm">
          {rows.map((row) => (
            <li key={row.key} className="flex items-center justify-between gap-3 py-2">
              <span dir="auto" className="truncate">{row.name}</span>
              <span className="flex shrink-0 items-center gap-2 tabular-nums">
                <Stars rating={row.average} label={starsLabel(row.average)} />
                <span className="font-semibold">{number.format(row.average)}</span>
                <span className="text-muted">({row.count})</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    );

  return (
    <section aria-labelledby="reviews-heading" className="flex flex-col gap-5 card p-6">
      <h2 id="reviews-heading" className="text-lg font-semibold">{title}</h2>
      {summary.count === 0 || summary.average === null ? (
        <p className="text-sm text-muted">{t("none")}</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-8">
            <div className="flex flex-col items-center gap-1">
              <span className="text-5xl font-bold tabular-nums">{number.format(summary.average)}</span>
              <Stars rating={summary.average} label={starsLabel(summary.average)} />
              <span className="text-xs text-muted">{t("count", { count: summary.count })}</span>
            </div>
            <ul className="flex min-w-56 flex-1 flex-col gap-1.5" aria-label={t("distribution")}>
              {[5, 4, 3, 2, 1].map((stars) => {
                const count = summary.distribution[stars - 1] ?? 0;
                return (
                  <li key={stars} className="flex items-center gap-2 text-xs">
                    <span className="w-14 shrink-0 tabular-nums">{t("starsShort", { count: stars })}</span>
                    <span aria-hidden="true" className="h-2 flex-1 overflow-hidden rounded-full bg-foreground/8">
                      <span className="block h-full rounded-full bg-amber-400" style={{ width: `${(count / most) * 100}%` }} />
                    </span>
                    <span className="w-8 shrink-0 text-end tabular-nums text-muted">{count}</span>
                  </li>
                );
              })}
            </ul>
          </div>
          {withGroups && (
            <div className="grid gap-6 md:grid-cols-2">
              {group(t("byStaff"), summary.by_staff)}
              {group(t("byService"), summary.by_service)}
            </div>
          )}
          {summary.latest.some((r) => r.comment) && (
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold">{t("comments")}</h3>
              <ul className="flex flex-col gap-2">
                {summary.latest
                  .filter((r) => r.comment)
                  .slice(0, 8)
                  .map((review) => (
                    <li key={review.id} className="flex flex-col gap-1 rounded-xl border border-border p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Stars rating={review.rating} label={starsLabel(review.rating)} />
                        <span className="text-xs text-muted">
                          {withClients && (
                            <>
                              <Link href={`/clients/${review.client_id}`} dir="auto" className="font-medium text-foreground underline-offset-4 hover:underline">
                                {review.client_name}
                              </Link>
                              {" · "}
                            </>
                          )}
                          {review.service_name}
                          {review.staff_name && ` · ${review.staff_name}`} · {when.format(new Date(review.created_at))}
                        </span>
                      </div>
                      <p dir="auto" className="text-sm">{review.comment}</p>
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  );
}
