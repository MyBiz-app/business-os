import { getLocale, getTranslations } from "next-intl/server";

import { ScrollRegion } from "@/components/scroll-region";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { getPlatformFor } from "@/lib/platform";

/** What MyBiz billed businesses, per month and currency. */
export default async function PlatformBillingPage() {
  const t = await getTranslations("platform");
  const locale = await getLocale();
  const { api } = await getPlatformFor("billing.manage");
  const billing = unwrap(await api.GET("/platform/billing"));
  const number = new Intl.NumberFormat(locale);
  const percent = new Intl.NumberFormat(locale, { style: "percent" });
  // One summary per currency (newest month first in the list).
  const summaries = [...new Set(billing.map((row) => row.currency))].map((currency) => {
    const rows = billing.filter((row) => row.currency === currency);
    return {
      currency,
      latest: rows[0],
      paid: rows.reduce((sum, row) => sum + row.paid, 0),
      open: rows.reduce((sum, row) => sum + row.open, 0),
    };
  });

  return (
    <main className="enter mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-col gap-1">
        <h1 id="billing-heading" className="text-3xl font-bold">
          {t("billing")}
        </h1>
        <p className="text-sm text-muted">{t("billingHint")}</p>
      </div>
      {billing.length === 0 ? (
        <p className="text-muted">{t("noBilling")}</p>
      ) : (
        <>
        {summaries.map((summary) => (
          <dl key={summary.currency} className="grid gap-3 sm:grid-cols-3">
            {(
              [
                [t("billingStats.lastMonth", { month: formatDay(summary.latest.month, locale, { month: "long" }) }), summary.latest.paid + summary.latest.open],
                [t("billingStats.paidTotal"), summary.paid],
                [t("billingStats.openTotal"), summary.open],
              ] as const
            ).map(([label, amount]) => (
              <div key={label} className="flex flex-col gap-1 card p-5">
                <dt className="text-sm text-muted">{label}</dt>
                <dd className="text-2xl font-bold tabular-nums">
                  <bdi>{formatMoney(amount, summary.currency, locale)}</bdi>
                </dd>
              </div>
            ))}
          </dl>
        ))}
        <ScrollRegion labelledBy="billing-heading" className="card">
          <table className="w-full text-sm">
            <thead className="text-muted">
              <tr className="border-b border-border">
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("month")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("invoices")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("paid")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("open")}</th>
              </tr>
            </thead>
            <tbody>
              {billing.map((row) => (
                <tr key={`${row.month}-${row.currency}`} className="border-b border-border last:border-0">
                  <td className="px-4 py-3">{formatDay(row.month, locale, { month: "long", year: "numeric" })}</td>
                  <td className="px-4 py-3 text-end tabular-nums">{number.format(row.invoices)}</td>
                  <td className="px-4 py-3 text-end tabular-nums">
                    <span className="flex items-center justify-end gap-2">
                      <span
                        role="img"
                        aria-label={t("billingStats.paidShare", { value: percent.format(row.paid / Math.max(1, row.paid + row.open)) })}
                        className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-foreground/8 sm:block"
                      >
                        <span className="block h-full rounded-full bg-success" style={{ inlineSize: `${(row.paid / Math.max(1, row.paid + row.open)) * 100}%` }} />
                      </span>
                      <bdi>{formatMoney(row.paid, row.currency, locale)}</bdi>
                    </span>
                  </td>
                  <td className="px-4 py-3 text-end tabular-nums"><bdi>{formatMoney(row.open, row.currency, locale)}</bdi></td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
        </>
      )}
    </main>
  );
}
