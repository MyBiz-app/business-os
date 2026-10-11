import { MessageCircle } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { formatMoney, toMajorUnits } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";
import { whatsappLink } from "@/lib/whatsapp";

import { copyQuote, sendQuote } from "../actions";
import { STATUS_TONE } from "../status";
import { CopyLink } from "./copy-link";
import { PaymentForm } from "./payment-form";

const WEB_URL = process.env.NEXT_PUBLIC_WEB_URL ?? "http://localhost:3000";

/** One quote: its lines and totals, sending it, the client's answer, payments. */
export default async function QuotePage({ params }: PageProps<"/quotes/[id]">) {
  const { id } = await params;
  const t = await getTranslations("quotes");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("clients.read");
  const { data: quote } = await api.GET("/quotes/{quote_id}", { params: { ...scope, path: { quote_id: id } } });
  if (!quote) notFound();
  const client = unwrap(await api.GET("/clients/{client_id}", { params: { ...scope, path: { client_id: quote.client_id } } }));
  const canSell = tenant.permissions.includes("sales.manage");
  const money = (amount: number) => formatMoney(amount, quote.currency, locale);
  const quantity = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "full", timeStyle: "short", timeZone: tenant.time_zone });
  const link = `${WEB_URL}/q/${quote.token}`;
  const whatsapp = client.phone
    ? whatsappLink(client.phone, tenant.time_zone, t("whatsappText", { name: client.first_name, title: quote.title, link }))
    : null;
  const due = quote.total - quote.paid;

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6">
      <Link href="/quotes" className="text-sm text-primary underline-offset-4 hover:underline">{t("back")}</Link>
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-bold">
            <span className="tabular-nums text-muted">#{quote.number}</span> <span dir="auto">{quote.title}</span>
          </h1>
          <Pill tone={STATUS_TONE[quote.status]}>{t(`statuses.${quote.status}`)}</Pill>
        </div>
        <p className="text-muted">
          <Link href={`/clients/${quote.client_id}`} dir="auto" className="underline-offset-4 hover:underline">{quote.client_name}</Link>
          {quote.event_starts_at && ` · ${when.format(new Date(quote.event_starts_at))}`}
          {quote.event_place && <span dir="auto"> · {quote.event_place}</span>}
        </p>
      </div>

      {canSell && (
        <section aria-labelledby="actions-heading" className="card flex flex-col gap-3 p-6">
          <h2 id="actions-heading" className="font-semibold">{t("share")}</h2>
          <div className="flex flex-wrap gap-2">
            {quote.status === "draft" && (
              <>
                <form action={sendQuote.bind(null, quote.id)}>
                  <button type="submit" className="btn-primary px-4 py-2">{t("send")}</button>
                </form>
                <Link href={`/quotes/${quote.id}/edit`} className="btn-secondary px-4 py-2">{t("edit")}</Link>
              </>
            )}
            {quote.status !== "draft" && <CopyLink url={link} />}
            {quote.status !== "draft" && whatsapp && (
              <a href={whatsapp} target="_blank" rel="noreferrer" className="btn-secondary px-3 py-2 text-sm">
                <MessageCircle aria-hidden="true" className="size-4" /> WhatsApp
              </a>
            )}
            {quote.status !== "draft" && (
              <a href={`/q/${quote.token}`} target="_blank" rel="noreferrer" className="btn-secondary px-3 py-2 text-sm">{t("preview")}</a>
            )}
            <form action={copyQuote.bind(null, quote.id)}>
              <button type="submit" className="btn-secondary px-3 py-2 text-sm">{t("copyAsNew")}</button>
            </form>
          </div>
          {quote.status === "draft" && <p className="text-sm text-muted">{t("draftHint")}</p>}
          {quote.status === "accepted" && (
            <p className="text-sm text-success">{t("acceptedBy", { name: quote.accepted_name ?? "", date: when.format(new Date(quote.accepted_at!)) })}</p>
          )}
        </section>
      )}

      <section aria-labelledby="lines-heading" className="card flex flex-col gap-4 p-6">
        <h2 id="lines-heading" className="font-semibold">{t("lines")}</h2>
        <table className="w-full text-sm">
          <thead className="text-muted">
            <tr>
              <th scope="col" className="pb-2 text-start font-medium">{t("description")}</th>
              <th scope="col" className="pb-2 text-end font-medium">{t("quantity")}</th>
              <th scope="col" className="pb-2 text-end font-medium">{t("unitPrice")}</th>
              <th scope="col" className="pb-2 text-end font-medium">{t("amount")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {quote.lines.map((line, index) => (
              <tr key={index}>
                <td dir="auto" className="py-2">{line.description}</td>
                <td className="py-2 text-end tabular-nums">{quantity.format(Number(line.quantity))}</td>
                <td className="py-2 text-end tabular-nums">{money(line.unit_price)}</td>
                <td className="py-2 text-end tabular-nums">{money(Math.round(Number(line.quantity) * line.unit_price))}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-border font-bold">
              <th scope="row" colSpan={3} className="pt-3 text-start">{t("total")}</th>
              <td className="pt-3 text-end tabular-nums">{money(quote.total)}</td>
            </tr>
          </tfoot>
        </table>
        <dl className="grid gap-2 text-sm sm:grid-cols-3">
          <div><dt className="text-muted">{t("deposit")}</dt><dd className="font-semibold">{quote.deposit_percent}%</dd></div>
          <div><dt className="text-muted">{t("paid")}</dt><dd className="font-semibold tabular-nums">{money(quote.paid)}</dd></div>
          <div><dt className="text-muted">{t("due")}</dt><dd className="font-semibold tabular-nums">{money(due)}</dd></div>
        </dl>
        {quote.notes && <p dir="auto" className="whitespace-pre-line text-sm text-muted">{quote.notes}</p>}
      </section>

      {canSell && quote.status === "accepted" && due > 0 && (
        <section aria-labelledby="payment-heading" className="card flex flex-col gap-3 p-6">
          <h2 id="payment-heading" className="font-semibold">{t("recordPayment")}</h2>
          <PaymentForm quoteId={quote.id} paymentKey={`quote-${quote.id}-${quote.paid}`} due={toMajorUnits(due, quote.currency)} currency={quote.currency} />
        </section>
      )}
    </main>
  );
}
