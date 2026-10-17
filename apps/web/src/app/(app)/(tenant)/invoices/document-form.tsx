"use client";

import { Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { Field, SelectField, TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { PAYMENT_METHODS, type DocumentKind } from "@/lib/issued-documents";

import type { IssueState } from "./actions";

type Line = { key: number; description: string; quantity: string; price: string };

type Props = {
  action: (state: IssueState, formData: FormData) => Promise<IssueState>;
  /** The kinds the business may start; a credit note passes only itself. */
  kinds: DocumentKind[];
  kind: DocumentKind;
  currency: string;
  clients: { id: string; name: string }[];
  clientId?: string;
  /** A credit note: the invoice it credits (fixed client, its lines to start from). */
  credit?: { id: string; label: string; clientName: string; lines: { description: string; quantity: string; price: string }[] };
  today: string;
};

const WITH_METHOD: DocumentKind[] = ["tax_invoice_receipt"];
const WITH_DUE: DocumentKind[] = ["tax_invoice", "transaction_invoice"];

/** The issue form: kind, client, lines (VAT included for tax documents), then the fields that
 * kind uses. Nothing is saved until "Issue"; an issued document cannot be edited. */
export function DocumentForm({ action, kinds, kind: initialKind, currency, clients, clientId, credit, today }: Props) {
  const t = useTranslations("invoices");
  const [state, formAction] = useActionState(action, {});
  const [kind, setKind] = useState<DocumentKind>(initialKind);
  const [lines, setLines] = useState<Line[]>(() =>
    (credit?.lines.length ? credit.lines : [{ description: "", quantity: "1", price: "" }]).map((l, i) => ({ ...l, key: i })),
  );
  const [next, setNext] = useState(lines.length);
  const total = lines.reduce((sum, l) => sum + (Number(l.quantity) || 0) * (Number(l.price.replace(",", ".")) || 0), 0);
  const update = (key: number, field: "description" | "quantity" | "price", value: string) =>
    setLines((current) => current.map((l) => (l.key === key ? { ...l, [field]: value } : l)));

  return (
    <form action={formAction} className="flex flex-col gap-5">
      <FormFeedback state={state.reason ? { ...state, error: undefined } : state} />
      <FormError message={state.reason && t(`reasons.${state.reason}`)} />
      {credit ? (
        <>
          <input type="hidden" name="kind" value="credit_note" />
          <input type="hidden" name="reference_id" value={credit.id} />
          <p className="rounded-xl bg-primary/10 px-3 py-2 text-sm">{t("creditFor", { number: credit.label, client: credit.clientName })}</p>
        </>
      ) : (
        <>
          <SelectField
            label={t("kind")}
            name="kind"
            value={kind}
            onChange={(e) => setKind(e.target.value as DocumentKind)}
            options={kinds.map((k) => ({ value: k, label: t(`kinds.${k}`) }))}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField
              label={t("client")}
              name="client_id"
              defaultValue={clientId ?? ""}
              options={[{ value: "", label: t("noClient") }, ...clients.map((c) => ({ value: c.id, label: c.name }))]}
            />
            <Field label={t("clientName")} hint={t("clientNameHint")} name="client_name" maxLength={200} dir="auto" />
            <Field label={t("clientEmail")} name="client_email" type="email" maxLength={200} />
            <Field label={t("clientTaxId")} hint={t("clientTaxIdHint")} name="client_tax_id" maxLength={20} dir="ltr" />
          </div>
        </>
      )}

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1 font-semibold">{t("lines")}</legend>
        <p className="text-sm text-muted">{kind === "quote" || kind === "transaction_invoice" ? t("pricesNoVat") : t("pricesWithVat")}</p>
        {lines.map((line, index) => (
          <div key={line.key} className="grid items-end gap-2 rounded-xl border border-border p-3 sm:grid-cols-[1fr_6rem_8rem_auto]">
            <Field
              label={t("lineDescription", { number: index + 1 })}
              name={`line.${index}.description`}
              required
              maxLength={300}
              dir="auto"
              value={line.description}
              onChange={(e) => update(line.key, "description", e.target.value)}
            />
            <Field
              label={t("quantity")}
              name={`line.${index}.quantity`}
              inputMode="decimal"
              dir="ltr"
              required
              value={line.quantity}
              onChange={(e) => update(line.key, "quantity", e.target.value)}
            />
            <Field
              label={`${t("unitPrice")} (${currency})`}
              name={`line.${index}.price`}
              inputMode="decimal"
              dir="ltr"
              required
              pattern="\d+([.,]\d{1,2})?"
              value={line.price}
              onChange={(e) => update(line.key, "price", e.target.value)}
            />
            <button
              type="button"
              aria-label={t("removeLine", { number: index + 1 })}
              disabled={lines.length === 1}
              onClick={() => setLines((current) => current.filter((l) => l.key !== line.key))}
              className="mb-1 rounded-lg p-2 text-muted hover:bg-danger/10 hover:text-danger disabled:opacity-40"
            >
              <Trash2 aria-hidden="true" className="size-4" />
            </button>
          </div>
        ))}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => {
              setLines((current) => [...current, { key: next, description: "", quantity: "1", price: "" }]);
              setNext(next + 1);
            }}
            className="btn-secondary px-3 py-1.5 text-sm"
          >
            <Plus aria-hidden="true" className="size-4" /> {t("addLine")}
          </button>
          <p className="font-semibold" aria-live="polite">
            {t("total")}: <span className="tabular-nums" dir="ltr">{total.toFixed(2)} {currency}</span>
          </p>
        </div>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        {WITH_METHOD.includes(kind) && !credit && (
          <SelectField
            label={t("paymentMethod")}
            name="payment_method"
            defaultValue="card"
            options={PAYMENT_METHODS.map((m) => ({ value: m, label: t(`methods.${m}`) }))}
          />
        )}
        {WITH_DUE.includes(kind) && !credit && <Field label={t("dueDate")} name="due_date" type="date" min={today} />}
        {kind === "quote" && <Field label={t("validUntil")} name="valid_until" type="date" min={today} />}
        {kind !== "credit_note" && !WITH_METHOD.includes(kind) && (
          <div className="sm:col-span-2">
            <Field label={t("paymentTerms")} name="payment_terms" maxLength={300} dir="auto" />
          </div>
        )}
        <div className="sm:col-span-2">
          <TextAreaField label={t("notes")} name="notes" rows={3} maxLength={1000} />
        </div>
      </div>
      <p className="text-sm text-muted">{t("issueHint")}</p>
      <div>
        <SubmitButton>{t("issue")}</SubmitButton>
      </div>
    </form>
  );
}
