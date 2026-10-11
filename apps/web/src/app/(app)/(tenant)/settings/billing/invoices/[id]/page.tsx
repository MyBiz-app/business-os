import { BRAND } from "@business-os/i18n/brand";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { ApiError, unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { PrintButton } from "@/components/print-button";

/** A MyBiz invoice to the business, laid out as a printable document. */
export default async function PlatformInvoicePage({ params }: PageProps<"/settings/billing/invoices/[id]">) {
  const { id } = await params;
  const t = await getTranslations("billing");
  const tModules = await getTranslations("modules");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  if (!canManageSettings(tenant)) redirect("/dashboard");
  let invoice;
  try {
    invoice = unwrap(await api.GET("/billing/invoices/{invoice_id}", { params: { ...scope, path: { invoice_id: id } } }));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  const money = (amount: number) => formatMoney(amount, invoice.currency, locale);
  const day = (value: string) => formatDay(value, locale, { day: "numeric", month: "long", year: "numeric" });
  const label = (key: string) => (key === "core" ? tModules("core") : tModules(`names.${key as "client_app"}`));

  return (
    <main className="enter mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-6 py-10 print:max-w-none print:p-0">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link href="/settings/billing" className="text-sm text-primary underline-offset-4 hover:underline">
          {t("back")}
        </Link>
        <PrintButton label={t("print")} />
      </div>

      <article className="card flex flex-col gap-8 p-8 sm:p-10 print:border-0 print:shadow-none">
        {invoice.simulated && (
          <p role="note" className="rounded-xl border border-warning/50 bg-warning/10 px-4 py-2 text-center text-sm font-semibold">
            {t("sample")}
          </p>
        )}
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-2xl font-bold">{BRAND.name}</p>
            <h1 className="text-lg font-semibold text-muted">{t("invoiceTitle", { number: invoice.number })}</h1>
          </div>
          <dl className="grid grid-cols-[auto_auto] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted">{t("issuedAt")}</dt>
            <dd>{day(invoice.issued_at.slice(0, 10))}</dd>
            <dt className="text-muted">{t("period")}</dt>
            <dd>{day(invoice.period_start)} – {day(invoice.period_end)}</dd>
            <dt className="text-muted">{t("to")}</dt>
            <dd dir="auto">{invoice.billing.billing_name ?? invoice.business_name}</dd>
            {invoice.billing.tax_id && (
              <>
                <dt className="text-muted">{t("taxId")}</dt>
                <dd dir="ltr">{invoice.billing.tax_id}</dd>
              </>
            )}
          </dl>
        </header>

        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-muted">
              <th scope="col" className="py-2 text-start font-medium">{t("item")}</th>
              <th scope="col" className="py-2 text-end font-medium">{t("amount")}</th>
            </tr>
          </thead>
          <tbody>
            {invoice.lines.map((line) => (
              <tr key={line.key} className="border-b border-border">
                <td className="py-3">
                  {label(line.key)}
                  {line.key === "core" && (
                    <span className="block text-xs text-muted">{t("activeClients", { count: invoice.active_clients })}</span>
                  )}
                  {line.quantity > 1 && <span className="text-muted"> × {line.quantity}</span>}
                </td>
                <td className="py-3 text-end tabular-nums"><bdi>{money(line.amount)}</bdi></td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className="pt-4 text-start text-base font-semibold">{t("total")}</th>
              <td className="pt-4 text-end text-xl font-bold tabular-nums"><bdi>{money(invoice.total)}</bdi></td>
            </tr>
          </tfoot>
        </table>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4 text-sm text-muted">
          <span>
            {invoice.status === "paid" && invoice.paid_at
              ? t("paidWith", { last4: invoice.card_last4 ?? "", date: day(invoice.paid_at.slice(0, 10)) })
              : t(`statuses.${invoice.status}`)}
          </span>
        </footer>
      </article>
    </main>
  );
}
