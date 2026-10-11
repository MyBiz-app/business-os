import { Clock, FileText, Trash2 } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { todayIn } from "@/lib/dates";
import { formatMoney, toMajorUnits } from "@/lib/money";
import { canWriteClients } from "@/lib/permissions";
import type { getTenant } from "@/lib/tenant";

import { deleteDocument, updateDocument } from "./work-actions";
import { BillForm, DocumentForm, RetainerForm, TimeForm } from "./work-forms";

type Context = Awaited<ReturnType<typeof getTenant>>;
type Props = { clientId: string; context: Context; locked: boolean };

const hours = (minutes: number, locale: string) => new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(minutes / 60);

/** The client's documents (#45): upload, share with the client, ask to sign. */
export async function DocumentsSection({ clientId, context, locked }: Props) {
  const { api, scope, tenant } = context;
  const documents = unwrap(await api.GET("/clients/{client_id}/documents", { params: { ...scope, path: { client_id: clientId } } }));
  const t = await getTranslations("documents");
  const locale = await getLocale();
  const writable = !locked && canWriteClients(tenant);
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tenant.time_zone });
  const size = new Intl.NumberFormat(locale, { style: "unit", unit: "kilobyte", maximumFractionDigits: 0 });

  return (
    <section aria-labelledby="documents-heading" className="flex flex-col gap-4 card p-6">
      <h2 id="documents-heading" className="flex items-center gap-2 text-lg font-semibold">
        <FileText aria-hidden="true" className="size-5 text-primary" />
        {t("title")}
      </h2>
      {documents.length === 0 && <p className="text-sm text-muted">{t("none")}</p>}
      <ul className="flex flex-col divide-y divide-border">
        {documents.map((document) => (
          <li key={document.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
            <div className="flex min-w-0 flex-col gap-0.5">
              <a href={`/documents/${document.id}/file`} className="truncate font-medium text-primary underline-offset-4 hover:underline" dir="auto">
                {document.name}
              </a>
              <span className="text-xs text-muted">
                {t(`kinds.${document.kind}`)} · {date.format(new Date(document.created_at))} · {size.format(Math.max(1, Math.round(document.size / 1024)))}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {document.uploaded_by_client && <Pill tone="primary">{t("fromClient")}</Pill>}
              {document.shared && !document.uploaded_by_client && <Pill tone="muted">{t("shared")}</Pill>}
              {document.sign_requested &&
                (document.signed_at ? (
                  <Pill tone="success">{t("signedBy", { name: document.signed_name ?? "", date: date.format(new Date(document.signed_at)) })}</Pill>
                ) : (
                  <Pill tone="warning">{t("waitingSignature")}</Pill>
                ))}
              {writable && !document.uploaded_by_client && (
                <form action={updateDocument.bind(null, clientId, document.id, { shared: !document.shared })}>
                  <button type="submit" className="btn-secondary px-2.5 py-1 text-xs">{document.shared ? t("unshare") : t("share")}</button>
                </form>
              )}
              {writable && (
                <form action={deleteDocument.bind(null, clientId, document.id)}>
                  <button type="submit" aria-label={t("delete", { name: document.name })} className="rounded-lg p-1 text-muted hover:bg-danger/10 hover:text-danger">
                    <Trash2 aria-hidden="true" className="size-4" />
                  </button>
                </form>
              )}
            </div>
          </li>
        ))}
      </ul>
      {writable && (
        <details className="rounded-xl bg-foreground/[0.03] p-3">
          <summary className="cursor-pointer text-sm font-medium text-primary">{t("add")}</summary>
          <div className="pt-3">
            <DocumentForm clientId={clientId} />
          </div>
        </details>
      )}
    </section>
  );
}

/** Time worked for the client, the retainer and billing a month (#45). */
export async function TimeSection({ clientId, context, locked }: Props) {
  const { api, scope, tenant } = context;
  const path = { client_id: clientId };
  const [entries, retainer] = await Promise.all([
    api.GET("/time", { params: { ...scope, query: { client_id: clientId } } }).then(unwrap),
    api.GET("/clients/{client_id}/retainer", { params: { ...scope, path } }).then(unwrap),
  ]);
  const t = await getTranslations("time");
  const locale = await getLocale();
  const canSell = !locked && tenant.permissions.includes("sales.manage");
  const today = todayIn(tenant.time_zone);
  const unbilled = entries.filter((e) => e.billable && !e.bill_id).reduce((sum, e) => sum + e.minutes, 0);
  const date = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" });
  const months = [0, 1, 2].map((back) => {
    const d = new Date(`${today.slice(0, 7)}-15T12:00:00Z`);
    d.setUTCMonth(d.getUTCMonth() - back);
    const value = d.toISOString().slice(0, 7);
    return { value, label: new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" }).format(d) };
  });
  const money = (amount: number) => formatMoney(amount, tenant.currency, locale);

  return (
    <section aria-labelledby="time-heading" className="flex flex-col gap-4 card p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="time-heading" className="flex items-center gap-2 text-lg font-semibold">
          <Clock aria-hidden="true" className="size-5 text-primary" />
          {t("title")}
        </h2>
        <span className="text-sm text-muted">{t("unbilled", { hours: hours(unbilled, locale) })}</span>
      </div>
      {retainer && retainer.active && (
        <p className="text-sm">
          {retainer.monthly_amount > 0
            ? t("retainer.summary", { amount: money(retainer.monthly_amount), hours: hours(retainer.included_minutes, locale), rate: money(retainer.hourly_rate) })
            : t("retainer.hourly", { rate: money(retainer.hourly_rate) })}
        </p>
      )}
      {!locked && <TimeForm clientId={clientId} today={today} />}
      {entries.length === 0 ? (
        <p className="text-sm text-muted">{t("none")}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border text-sm">
          {entries.slice(0, 15).map((entry) => (
            <li key={entry.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span className="flex min-w-0 flex-col">
                <span dir="auto">{entry.description}</span>
                <span className="text-xs text-muted">{date.format(new Date(`${entry.day}T12:00:00`))} · {entry.user_name}</span>
              </span>
              <span className="flex items-center gap-2">
                <span className="tabular-nums">{t("hoursShort", { hours: hours(entry.minutes, locale) })}</span>
                {entry.bill_id ? (
                  <Link href={`/quotes/${entry.bill_id}`} className="text-xs text-primary underline-offset-4 hover:underline">{t("billed", { number: entry.bill_number ?? 0 })}</Link>
                ) : !entry.billable ? (
                  <Pill tone="muted">{t("notBillable")}</Pill>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      )}
      {canSell && (
        <div className="flex flex-col gap-4 border-t border-border pt-4">
          <BillForm clientId={clientId} months={months} />
          <details>
            <summary className="cursor-pointer text-sm font-medium text-primary">{t("retainer.edit")}</summary>
            <div className="pt-3">
              <RetainerForm
                clientId={clientId}
                currency={tenant.currency}
                values={{
                  monthly: retainer ? toMajorUnits(retainer.monthly_amount, tenant.currency) : "",
                  included_hours: retainer ? String(retainer.included_minutes / 60) : "",
                  rate: retainer ? toMajorUnits(retainer.hourly_rate, tenant.currency) : "",
                }}
              />
            </div>
          </details>
        </div>
      )}
    </section>
  );
}
