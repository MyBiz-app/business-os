import { CreditCard, FlaskConical, Receipt, Sparkles } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Pill } from "@/components/pill";
import { SubmitButton } from "@/components/form/submit-button";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { addTestCard, payInvoice, removeCard } from "./actions";
import { DetailsForm } from "./details-form";
import { ScrollRegion } from "@/components/scroll-region";

const TRIAL_DAYS = 14;
const BRANDS = ["visa", "mastercard", "amex"] as const;

export default async function BillingPage() {
  const t = await getTranslations("billing");
  const tModules = await getTranslations("modules");
  const tSettings = await getTranslations("settings");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const billing = unwrap(await api.GET("/billing", { params: scope }));
  const money = (amount: number, currency = billing.estimate.currency) => formatMoney(amount, currency, locale);
  const day = (value: string) => formatDay(value, locale, { day: "numeric", month: "long", year: "numeric" });
  const method = billing.payment_method;
  const estimateLines = [
    { key: "core", label: tModules("core"), amount: billing.estimate.core },
    ...Object.entries(billing.estimate.lines).map(([key, amount]) => ({
      key,
      label: tModules(`names.${key as "client_app"}`),
      amount: amount ?? 0,
    })),
  ];

  return (
    <main className="enter mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/settings" className="text-sm text-primary underline-offset-4 hover:underline">
        {tSettings("title")}
      </Link>
      <div className="flex items-center gap-3">
        <span className="icon-tile size-11">
          <CreditCard aria-hidden="true" className="size-5" />
        </span>
        <div className="flex flex-col gap-0.5">
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <p className="text-sm text-muted">{t("subtitle")}</p>
        </div>
      </div>

      <p role="note" className="flex items-center gap-2 rounded-xl border border-warning/50 bg-warning/10 px-4 py-2 text-sm">
        <FlaskConical aria-hidden="true" className="size-4 shrink-0" />
        {t("simulated")}
      </p>

      <section aria-labelledby="status-heading" className="card-accent flex flex-col gap-4 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="status-heading" className="flex items-center gap-2 text-xl font-bold">
            <Sparkles aria-hidden="true" className="size-5 text-primary" />
            {billing.in_trial ? t("trialLeft", { days: billing.trial_days_left }) : t("active")}
          </h2>
          <span className="text-sm text-muted">
            {billing.in_trial
              ? t("firstInvoice", { date: day(billing.next_invoice_on) })
              : t("nextInvoice", { date: day(billing.next_invoice_on) })}
          </span>
        </div>
        {billing.in_trial && (
          <div
            role="progressbar"
            aria-label={t("trialProgress")}
            aria-valuemin={0}
            aria-valuemax={TRIAL_DAYS}
            aria-valuenow={TRIAL_DAYS - billing.trial_days_left}
            className="h-2 overflow-hidden rounded-full bg-foreground/10"
          >
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${Math.round(((TRIAL_DAYS - billing.trial_days_left) / TRIAL_DAYS) * 100)}%` }}
            />
          </div>
        )}
        {billing.balance_due > 0 && (
          <p role="alert" className="rounded-xl border border-danger/40 bg-danger/10 px-4 py-2 text-sm font-medium">
            {t("balanceDue", { amount: money(billing.balance_due) })}
          </p>
        )}
      </section>

      <div className="grid gap-6 md:grid-cols-2">
        <section aria-labelledby="plan-heading" className="card flex flex-col gap-4 p-6">
          <div className="flex items-center justify-between gap-3">
            <h2 id="plan-heading" className="text-lg font-semibold">{t("plan")}</h2>
            <Link href="/settings/modules" className="text-sm text-primary underline-offset-4 hover:underline">
              {t("changeModules")}
            </Link>
          </div>
          <ul className="flex flex-col divide-y divide-border text-sm">
            {estimateLines.map((line) => (
              <li key={line.key} className="flex items-center justify-between gap-3 py-2">
                <span>{line.label}</span>
                <bdi className="tabular-nums">{money(line.amount)}</bdi>
              </li>
            ))}
          </ul>
          <p className="flex items-baseline justify-between gap-3 border-t border-border pt-3">
            <span className="font-semibold">{t("perMonth")}</span>
            <bdi className="text-2xl font-bold tabular-nums">{money(billing.estimate.total)}</bdi>
          </p>
        </section>

        <section aria-labelledby="method-heading" className="card flex flex-col gap-4 p-6">
          <h2 id="method-heading" className="text-lg font-semibold">{t("paymentMethod")}</h2>
          {method ? (
            <>
              <div
                dir="ltr"
                className="relative flex aspect-[1.7] max-w-xs flex-col justify-between overflow-hidden rounded-2xl bg-gradient-to-br from-zinc-800 to-zinc-950 p-5 text-white shadow-lg"
              >
                <span aria-hidden="true" className="absolute -end-10 -top-10 size-36 rounded-full bg-white/10" />
                <span className="flex items-center justify-between">
                  <span className="text-sm font-semibold uppercase tracking-wide">{t(`brands.${method.brand}`)}</span>
                  {method.simulated && (
                    <span className="rounded-full bg-amber-300 px-2 py-0.5 text-xs font-bold text-zinc-950">{t("testCard")}</span>
                  )}
                </span>
                <span className="font-mono text-lg tracking-widest">•••• •••• •••• {method.last4}</span>
                <span className="text-xs opacity-80">{method.exp}</span>
              </div>
              <form action={removeCard}>
                <button type="submit" className="text-sm text-danger underline-offset-4 hover:underline">
                  {t("removeCard")}
                </button>
              </form>
            </>
          ) : (
            <form action={addTestCard} className="flex flex-col gap-3">
              <p className="text-sm text-muted">{t("noCard")}</p>
              <label className="flex flex-col gap-1.5 text-sm font-medium">
                {t("brand")}
                <select name="brand" defaultValue="visa" className="control px-3 py-2 font-normal">
                  {BRANDS.map((brand) => (
                    <option key={brand} value={brand}>
                      {t(`brands.${brand}`)}
                    </option>
                  ))}
                </select>
              </label>
              <div>
                <SubmitButton>{t("addTestCard")}</SubmitButton>
              </div>
            </form>
          )}
        </section>
      </div>

      <section aria-labelledby="details-heading" className="card flex flex-col gap-4 p-6">
        <h2 id="details-heading" className="text-lg font-semibold">{t("details")}</h2>
        <DetailsForm details={billing.details} />
      </section>

      <section aria-labelledby="invoices-heading" className="card flex flex-col gap-4 p-6">
        <h2 id="invoices-heading" className="flex items-center gap-2 text-lg font-semibold">
          <Receipt aria-hidden="true" className="size-5 text-primary" />
          {t("invoices")}
        </h2>
        {billing.invoices.length === 0 ? (
          <p className="text-sm text-muted">{t("noInvoices")}</p>
        ) : (
          <ScrollRegion labelledBy="invoices-heading">
            <table className="w-full text-sm">
              <thead className="text-muted">
                <tr className="border-b border-border">
                  <th scope="col" className="py-2 text-start font-medium">{t("number")}</th>
                  <th scope="col" className="py-2 text-start font-medium">{t("period")}</th>
                  <th scope="col" className="py-2 text-start font-medium">{t("status")}</th>
                  <th scope="col" className="py-2 text-end font-medium">{t("total")}</th>
                  <th scope="col" className="py-2"><span className="sr-only">{t("actions")}</span></th>
                </tr>
              </thead>
              <tbody>
                {billing.invoices.map((invoice) => (
                  <tr key={invoice.id} className="border-b border-border last:border-0">
                    <td className="py-3 tabular-nums">{invoice.number}</td>
                    <td className="py-3">
                      {formatDay(invoice.period_start, locale, { day: "numeric", month: "short" })} –{" "}
                      {formatDay(invoice.period_end, locale, { day: "numeric", month: "short", year: "numeric" })}
                    </td>
                    <td className="py-3">
                      <Pill tone={invoice.status === "paid" ? "success" : invoice.status === "open" ? "danger" : "muted"}>
                        {t(`statuses.${invoice.status}`)}
                      </Pill>
                    </td>
                    <td className="py-3 text-end tabular-nums"><bdi>{money(invoice.total, invoice.currency)}</bdi></td>
                    <td className="py-3 text-end">
                      <span className="inline-flex items-center gap-3">
                        {invoice.status === "open" && method && (
                          <form action={payInvoice.bind(null, invoice.id)}>
                            <button type="submit" className="font-semibold text-primary underline-offset-4 hover:underline">
                              {t("pay")}
                            </button>
                          </form>
                        )}
                        <Link
                          href={`/settings/billing/invoices/${invoice.id}`}
                          className="text-primary underline-offset-4 hover:underline"
                          aria-label={t("viewInvoice", { number: invoice.number })}
                        >
                          {t("view")}
                        </Link>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        )}
      </section>
    </main>
  );
}
