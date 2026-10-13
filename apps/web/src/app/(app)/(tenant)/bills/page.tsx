import { Receipt } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";

import { unwrap } from "@/lib/api";
import { todayIn } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

import { RunForm } from "./run-form";

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;

/** Billing the month (#45): every client with a retainer or unbilled time, what each would be
 * billed, and one action that bills the chosen ones. Last month by default. */
export default async function BillsPage({ searchParams }: PageProps<"/bills">) {
  const t = await getTranslations("billingRun");
  const tTime = await getTranslations("time");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("sales.manage");
  const today = todayIn(tenant.time_zone);
  const months = [1, 0, 2, 3].map((back) => {
    const d = new Date(`${today.slice(0, 7)}-15T12:00:00Z`);
    d.setUTCMonth(d.getUTCMonth() - back);
    return {
      value: d.toISOString().slice(0, 7),
      label: new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" }).format(d),
    };
  });
  const requested = (await searchParams).month;
  const month = typeof requested === "string" && MONTH.test(requested) ? requested : months[0].value;
  const preview = unwrap(await api.GET("/bills/preview", { params: { ...scope, query: { month } } }));
  const hours = (minutes: number) =>
    tTime("hoursShort", { hours: new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(minutes / 60) });
  const money = (amount: number) => formatMoney(amount, tenant.currency, locale);
  const toBill = preview.filter((row) => !row.billed && row.total > 0);

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            <Receipt aria-hidden="true" className="size-8 shrink-0 text-primary" />
            {t("title")}
          </span>
        }
        description={t("subtitle")}
      />
      <form className="flex flex-wrap items-end gap-3" aria-label={t("chooseMonth")}>
        <label className="flex flex-col gap-1 text-sm font-medium">
          {tTime("month")}
          <select name="month" defaultValue={month} className="input">
            {months.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn-secondary px-4 py-2.5">
          {t("show")}
        </button>
      </form>
      <ul className="grid gap-3 sm:grid-cols-3">
        {[
          { label: t("clientsToBill"), value: String(toBill.length) },
          { label: t("totalToBill"), value: money(toBill.reduce((sum, row) => sum + row.total, 0)) },
          { label: t("alreadyBilled"), value: String(preview.filter((row) => row.billed).length) },
        ].map((stat) => (
          <li key={stat.label} className="flex flex-col rounded-2xl border border-border bg-surface px-4 py-3">
            <span className="text-xs text-muted">{stat.label}</span>
            <span className="text-2xl font-bold tabular-nums">{stat.value}</span>
          </li>
        ))}
      </ul>
      {preview.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("none")}</p>
      ) : (
        <RunForm
          key={month}
          month={month}
          rows={preview.map((row) => ({
            clientId: row.client_id,
            name: row.client_name,
            fee: row.monthly_amount ? money(row.monthly_amount) : null,
            hours: hours(row.worked_minutes),
            extra: row.extra_minutes && row.hourly_rate ? `${hours(row.extra_minutes)} × ${money(row.hourly_rate)}` : null,
            total: money(row.total),
            billable: row.total > 0,
            billed: row.billed,
          }))}
        />
      )}
    </Container>
  );
}
