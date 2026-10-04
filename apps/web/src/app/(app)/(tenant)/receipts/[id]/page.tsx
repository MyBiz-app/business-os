import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ApiError, unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";

import { PrintButton } from "./print-button";

/** A payment's receipt, laid out as a printable document. */
export default async function ReceiptPage({ params }: PageProps<"/receipts/[id]">) {
  const { id } = await params;
  const t = await getTranslations("receipts");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("clients.read");
  let receipt;
  try {
    receipt = unwrap(await api.GET("/receipts/{receipt_id}", { params: { ...scope, path: { receipt_id: id } } }));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  const issued = new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: tenant.time_zone }).format(
    new Date(receipt.issued_at),
  );
  const amount = formatMoney(receipt.amount, receipt.currency, locale);

  return (
    <main className="enter mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-6 py-10 print:max-w-none print:p-0">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link href={`/clients/${receipt.client_id}`} className="text-sm text-primary underline-offset-4 hover:underline">
          {t("back")}
        </Link>
        <PrintButton label={t("print")} />
      </div>

      <article className="card relative flex flex-col gap-8 overflow-hidden p-8 sm:p-10 print:border-0 print:shadow-none">
        {receipt.simulated && (
          <p role="note" className="rounded-xl border border-warning/50 bg-warning/10 px-4 py-2 text-center text-sm font-semibold">
            {t("sample")}
          </p>
        )}
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-2xl font-bold" dir="auto">{receipt.business_name}</p>
            <h1 className="text-lg font-semibold text-muted">{t("title", { number: receipt.number })}</h1>
          </div>
          <dl className="grid grid-cols-[auto_auto] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted">{t("issuedAt")}</dt>
            <dd>{issued}</dd>
            <dt className="text-muted">{t("to")}</dt>
            <dd dir="auto">{receipt.client_name}</dd>
            {receipt.client_email && (
              <>
                <dt className="sr-only">Email</dt>
                <dd className="col-start-2 text-muted" dir="ltr">{receipt.client_email}</dd>
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
            <tr className="border-b border-border">
              <td className="py-3" dir="auto">{receipt.description}</td>
              <td className="py-3 text-end tabular-nums">
                <bdi>{amount}</bdi>
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className="pt-4 text-start text-base font-semibold">{t("total")}</th>
              <td className="pt-4 text-end text-xl font-bold tabular-nums">
                <bdi>{amount}</bdi>
              </td>
            </tr>
          </tfoot>
        </table>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4 text-sm text-muted">
          <span>
            {t("method")}: {t(`methods.${receipt.method}`)}
          </span>
          <span>{t("thanks")}</span>
        </footer>
      </article>
    </main>
  );
}
