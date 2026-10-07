import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { AppHeader } from "@/components/app-header";
import { Pill, type Tone } from "@/components/pill";
import { getApi } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { brandStyle } from "@/lib/brand";
import { formatMoney } from "@/lib/money";

import { payDeposit } from "./actions";
import { AnswerForm } from "./answer-form";

const TONE: Record<string, Tone> = { sent: "primary", accepted: "success", declined: "muted", expired: "warning" };

async function quote(token: string) {
  const { data } = await (await getApi()).GET("/public/quotes/{token}", { params: { path: { token } } });
  return data;
}

export async function generateMetadata({ params }: PageProps<"/q/[token]">): Promise<Metadata> {
  const found = await quote((await params).token);
  const t = await getTranslations("quotes.public");
  return {
    title: found ? `${t("title", { number: found.number })} · ${isolate(found.business_name)}` : t("missing"),
    robots: { index: false },
  };
}

/** A quote by its private link (#44): no sign-in; the client reads it, accepts or declines it,
 * and pays the deposit. */
export default async function PublicQuotePage({ params, searchParams }: PageProps<"/q/[token]">) {
  const { token } = await params;
  const paidReturn = (await searchParams).paid === "1";
  const found = await quote(token);
  if (!found) notFound();
  const t = await getTranslations("quotes");
  const locale = await getLocale();
  const money = (amount: number) => formatMoney(amount, found.currency, locale);
  const quantity = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
  const deposit = Math.round((found.total * found.deposit_percent) / 100);
  const event = found.event_starts_at
    ? new Intl.DateTimeFormat(locale, { dateStyle: "full", timeStyle: "short", timeZone: found.time_zone }).format(new Date(found.event_starts_at))
    : null;
  const validUntil = found.valid_until
    ? new Intl.DateTimeFormat(locale, { dateStyle: "long" }).format(new Date(`${found.valid_until}T12:00:00`))
    : null;

  return (
    <div className="brand flex flex-1 flex-col" style={brandStyle(found.business_color)}>
      <AppHeader />
      <main className="enter mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
        <div className="flex flex-col gap-1">
          <p dir="auto" className="text-sm font-semibold text-primary">{found.business_name}</p>
          <div className="flex flex-wrap items-center gap-3">
            <h1 dir="auto" className="text-3xl font-bold">{found.title}</h1>
            <Pill tone={TONE[found.status] ?? "muted"}>{t(`statuses.${found.status}`)}</Pill>
          </div>
          <p className="text-sm text-muted">
            {t("public.title", { number: found.number })} · {t("public.for", { name: found.client_name })}
          </p>
        </div>

        {paidReturn && found.deposit_due > 0 && (
          <p role="status" className="rounded-xl bg-surface px-4 py-3 text-sm">{t("public.processing")}</p>
        )}

        {(event || found.event_place) && (
          <section aria-labelledby="event-heading" className="card flex flex-col gap-1 p-6">
            <h2 id="event-heading" className="font-semibold">{t("event")}</h2>
            {event && <p>{event}</p>}
            {found.event_place && <p dir="auto" className="text-muted">{found.event_place}</p>}
          </section>
        )}

        <section aria-labelledby="lines-heading" className="card flex flex-col gap-4 p-6">
          <h2 id="lines-heading" className="font-semibold">{t("lines")}</h2>
          <table className="w-full text-sm">
            <thead className="text-start text-muted">
              <tr>
                <th scope="col" className="pb-2 text-start font-medium">{t("description")}</th>
                <th scope="col" className="pb-2 text-end font-medium">{t("quantity")}</th>
                <th scope="col" className="pb-2 text-end font-medium">{t("amount")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {found.lines.map((line, index) => (
                <tr key={index}>
                  <td dir="auto" className="py-2">{line.description}</td>
                  <td className="py-2 text-end tabular-nums">{quantity.format(Number(line.quantity))}</td>
                  <td className="py-2 text-end tabular-nums">{money(Math.round(Number(line.quantity) * line.unit_price))}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-border font-bold">
                <th scope="row" colSpan={2} className="pt-3 text-start">{t("total")}</th>
                <td className="pt-3 text-end tabular-nums">{money(found.total)}</td>
              </tr>
            </tfoot>
          </table>
          {found.deposit_percent > 0 && (
            <p className="text-sm">{t("depositOf", { percent: found.deposit_percent, amount: money(deposit) })}</p>
          )}
          {found.paid > 0 && (
            <p className="text-sm font-medium text-success">
              {t("paidSoFar", { amount: money(found.paid) })} · {t("balance", { amount: money(found.total - found.paid) })}
            </p>
          )}
          {found.notes && <p dir="auto" className="whitespace-pre-line text-sm text-muted">{found.notes}</p>}
          {validUntil && found.status === "sent" && <p className="text-sm text-muted">{t("validUntil", { date: validUntil })}</p>}
        </section>

        {found.status === "sent" && (
          <section aria-labelledby="answer-heading" className="card flex flex-col gap-4 p-6">
            <h2 id="answer-heading" className="font-semibold">{t("public.answer")}</h2>
            <AnswerForm token={token} />
          </section>
        )}

        {found.status === "accepted" && (
          <section aria-labelledby="accepted-heading" className="card flex flex-col gap-3 p-6">
            <h2 id="accepted-heading" className="font-semibold">
              {t("public.acceptedBy", { name: found.accepted_name ?? "" })}
            </h2>
            {found.deposit_due > 0 ? (
              <form action={payDeposit.bind(null, token, `deposit-${token.slice(0, 16)}-${found.paid}`)}>
                <button type="submit" className="btn-primary px-5 py-2.5">
                  {t("public.payDeposit", { amount: money(found.deposit_due) })}
                </button>
              </form>
            ) : (
              <p className="text-sm text-success">{t("public.depositPaid")}</p>
            )}
          </section>
        )}
        {found.status === "declined" && <p className="text-muted">{t("public.declined")}</p>}
        {found.status === "expired" && <p className="text-muted">{t("public.expired")}</p>}
      </main>
    </div>
  );
}
