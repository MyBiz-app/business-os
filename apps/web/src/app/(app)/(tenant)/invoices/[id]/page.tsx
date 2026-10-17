import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Ltr } from "@/components/bidi";
import { DownloadLink } from "@/components/download-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { ScrollRegion } from "@/components/scroll-region";
import { ApiError, unwrap } from "@/lib/api";
import { canCredit } from "@/lib/issued-documents";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";

/** One issued document: what it says, and its PDF (the stored original, or a marked copy). */
export default async function InvoicePage({ params }: PageProps<"/invoices/[id]">) {
  const { id } = await params;
  const t = await getTranslations("invoices");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("sales.manage");
  let doc;
  try {
    doc = unwrap(await api.GET("/issued-documents/{document_id}", { params: { ...scope, path: { document_id: id } } }));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  const money = (amount: number) => formatMoney(amount, doc.currency, locale);
  const day = (value: string) => new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: tenant.time_zone }).format(new Date(value));
  const showVat = doc.kind === "tax_invoice" || doc.kind === "tax_invoice_receipt" || doc.kind === "credit_note";
  const facts: [string, React.ReactNode][] = [
    [t("issuedAt"), day(doc.issued_at)],
    [t("client"), <span key="c" dir="auto">{doc.client_name}</span>],
    ...(doc.client_email ? ([[t("clientEmail"), <Ltr key="e">{doc.client_email}</Ltr>]] as [string, React.ReactNode][]) : []),
    ...(doc.client_tax_id ? ([[t("clientTaxId"), <Ltr key="x">{doc.client_tax_id}</Ltr>]] as [string, React.ReactNode][]) : []),
    ...(doc.payment_method ? ([[t("paymentMethod"), t(`methods.${doc.payment_method}`)]] as [string, React.ReactNode][]) : []),
    ...(doc.due_date ? ([[t("dueDate"), day(doc.due_date)]] as [string, React.ReactNode][]) : []),
    ...(doc.valid_until ? ([[t("validUntil"), day(doc.valid_until)]] as [string, React.ReactNode][]) : []),
    ...(doc.allocation_number ? ([[t("allocationNumber"), <Ltr key="a">{doc.allocation_number}</Ltr>]] as [string, React.ReactNode][]) : []),
  ];

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/invoices" className="text-sm text-primary underline-offset-4 hover:underline">{t("back")}</Link>
      <PageHeader
        title={
          <span>
            {t(`kinds.${doc.kind}`)} <Ltr className="tabular-nums">#{doc.number}</Ltr>
          </span>
        }
        actions={
          <>
            <DownloadLink href={`/invoices/${id}/pdf`} label={t("downloadOriginal")} />
            <DownloadLink href={`/invoices/${id}/pdf?copy=1`} label={t("downloadCopy")} />
            {canCredit(doc.kind) && (
              <Link href={`/invoices/new?credit=${id}`} className="btn-secondary px-4 py-2">{t("issueCredit")}</Link>
            )}
          </>
        }
      />
      <p role="note" className="rounded-xl border border-warning/50 bg-warning/10 px-4 py-2 text-sm">{t("sampleNote")}</p>
      {doc.allocation_required && !doc.allocation_number && (
        <p role="note" className="rounded-xl border border-warning/50 bg-warning/10 px-4 py-2 text-sm">{t("allocationNote")}</p>
      )}
      <section className="card p-6">
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
          {facts.map(([label, value]) => (
            <div key={label} className="flex flex-col gap-0.5">
              <dt className="text-sm text-muted">{label}</dt>
              <dd className="font-medium">{value}</dd>
            </div>
          ))}
        </dl>
      </section>
      <section aria-labelledby="lines-heading" className="flex flex-col gap-3">
        <h2 id="lines-heading" className="text-lg font-semibold">{t("lines")}</h2>
        <ScrollRegion labelledBy="lines-heading" className="rounded-2xl border border-border">
          <table className="w-full text-sm">
            <thead className="bg-surface text-muted">
              <tr>
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("description")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("quantity")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("unitPrice")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("amount")}</th>
              </tr>
            </thead>
            <tbody>
              {doc.lines.map((line, index) => (
                <tr key={index} className="border-t border-border">
                  <td className="px-4 py-2.5" dir="auto">{line.description}</td>
                  <td className="px-4 py-2.5 text-end tabular-nums">{line.quantity}</td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-end"><bdi>{money(line.unit_price)}</bdi></td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-end font-medium"><bdi>{money(line.amount)}</bdi></td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
        <dl className="ms-auto flex min-w-60 flex-col gap-1 text-sm">
          {showVat && (
            <>
              <div className="flex justify-between gap-6"><dt className="text-muted">{t("net")}</dt><dd><bdi>{money(doc.net)}</bdi></dd></div>
              <div className="flex justify-between gap-6">
                <dt className="text-muted">{t("vat", { rate: doc.vat_rate_bp / 100 })}</dt>
                <dd><bdi>{money(doc.vat)}</bdi></dd>
              </div>
            </>
          )}
          <div className="flex justify-between gap-6 text-base font-semibold"><dt>{t("total")}</dt><dd><bdi>{money(doc.total)}</bdi></dd></div>
        </dl>
      </section>
      {(doc.payment_terms || doc.notes) && (
        <section className="card flex flex-col gap-2 p-6 text-sm">
          {doc.payment_terms && <p dir="auto">{doc.payment_terms}</p>}
          {doc.notes && <p dir="auto">{doc.notes}</p>}
        </section>
      )}
      <p className="text-xs text-muted">
        {t("fingerprint")} <Ltr className="break-all">{doc.content_hash}</Ltr>
      </p>
    </Container>
  );
}
