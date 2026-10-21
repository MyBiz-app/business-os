import { DataTable } from "@/components/ui/data-table";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Ltr } from "@/components/bidi";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { getPlatformFor } from "@/lib/platform";
import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { SubmitButton } from "@/components/form/submit-button";

import { extendGrace } from "./actions";
import { DunningForm } from "./dunning-form";
import { StatTile } from "@/components/ui/stat-tile";

/** What MyBiz billed businesses, per month and currency. */
export default async function PlatformBillingPage() {
  const t = await getTranslations("platform");
  const locale = await getLocale();
  const { api } = await getPlatformFor("billing.manage");
  const billing = unwrap(await api.GET("/platform/billing"));
  const overdue = unwrap(await api.GET("/platform/billing/overdue"));
  const dunning = unwrap(await api.GET("/platform/billing/dunning"));
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
    <Container as="main" size="settings" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader titleId="billing-heading" title={t("billing")} description={t("billingHint")} />
      <section aria-labelledby="overdue-heading" className="flex flex-col gap-3">
        <h2 id="overdue-heading" className="text-lg font-semibold">{t("overdue.title")}</h2>
        <p className="text-sm text-muted">{t("overdue.hint")}</p>
        {overdue.length === 0 ? (
          <EmptyState variant="list">{t("overdue.empty")}</EmptyState>
        ) : (
          <DataTable
            labelledBy="overdue-heading"
            rows={overdue}
            rowKey={(row) => row.tenant_id}
            columns={[
              {
                key: "business",
                header: t("overdue.business"),
                cell: (row) => (
                  <Link dir="auto" href={`/platform/businesses/${row.tenant_id}`} className="text-primary-ink underline-offset-4 hover:underline">{row.name}</Link>
                ),
              },
              { key: "owner", header: t("overdue.owner"), cell: (row) => <Ltr>{row.owner_email ?? ""}</Ltr> },
              {
                key: "open",
                header: t("overdue.open"),
                align: "end",
                className: "tabular-nums",
                cell: (row) => <bdi>{formatMoney(row.open_amount, row.currency, locale)}</bdi>,
              },
              { key: "since", header: t("overdue.since"), cell: (row) => formatDay(row.oldest_issued_at, locale, { day: "numeric", month: "short", year: "numeric" }) },
              {
                key: "state",
                header: t("overdue.state"),
                cell: (row) => (
                  <>
                    <Pill tone={row.billing_state === "active" ? "muted" : "danger"}>{t(`overdue.states.${row.billing_state}`)}</Pill>
                    {row.grace_until && new Date(row.grace_until) > new Date() && (
                      <span className="block text-xs text-muted">{t("overdue.graceUntil", { date: formatDay(row.grace_until, locale, { day: "numeric", month: "short" }) })}</span>
                    )}
                  </>
                ),
              },
              {
                key: "action",
                header: t("overdue.action"),
                cell: (row) => (
                  <form action={extendGrace.bind(null, row.tenant_id)} className="flex items-end gap-2">
                    <label className="flex flex-col gap-1 text-xs text-muted">
                      {t("overdue.days")}
                      <input type="number" name="days" min={1} max={90} defaultValue={7} className="control w-20 px-2 py-1.5 text-sm" />
                    </label>
                    <SubmitButton className="px-3 py-1.5 text-sm">{t("overdue.extend")}</SubmitButton>
                  </form>
                ),
              },
            ]}
          />
        )}
      </section>
      <DunningForm settings={dunning} />
      {billing.length === 0 ? (
        <EmptyState variant="list">{t("noBilling")}</EmptyState>
      ) : (
        <>
        {summaries.map((summary) => (
          <div key={summary.currency} className="grid gap-3 sm:grid-cols-3">
            {(
              [
                [t("billingStats.lastMonth", { month: formatDay(summary.latest.month, locale, { month: "long" }) }), summary.latest.paid + summary.latest.open],
                [t("billingStats.paidTotal"), summary.paid],
                [t("billingStats.openTotal"), summary.open],
              ] as const
            ).map(([label, amount]) => (
              <StatTile key={label} label={label} value={<bdi>{formatMoney(amount, summary.currency, locale)}</bdi>} />
            ))}
          </div>
        ))}
        <DataTable
          labelledBy="billing-heading"
          rows={billing}
          rowKey={(row) => `${row.month}-${row.currency}`}
          columns={[
            { key: "month", header: t("month"), cell: (row) => formatDay(row.month, locale, { month: "long", year: "numeric" }) },
            { key: "invoices", header: t("invoices"), align: "end", className: "tabular-nums", cell: (row) => number.format(row.invoices) },
            {
              key: "paid",
              header: t("paid"),
              align: "end",
              className: "tabular-nums",
              cell: (row) => (
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
              ),
            },
            { key: "open", header: t("open"), align: "end", className: "tabular-nums", cell: (row) => <bdi>{formatMoney(row.open, row.currency, locale)}</bdi> },
          ]}
        />
        </>
      )}
    </Container>
  );
}
