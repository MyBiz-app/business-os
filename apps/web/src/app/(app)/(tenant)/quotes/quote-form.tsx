"use client";

import { Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { Field, SelectField, TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

type Line = { key: number; description: string; quantity: string; price: string };

export type QuoteDefaults = {
  title: string;
  lines: { description: string; quantity: string; price: string }[];
  deposit_percent: number;
  valid_until: string;
  event_date: string;
  event_time: string;
  event_place: string;
  notes: string;
};

type Props = {
  action: (state: FormState, formData: FormData) => Promise<FormState>;
  defaults: QuoteDefaults;
  currency: string;
  /** New quotes choose the client; editing keeps it. */
  clients?: { id: string; name: string }[];
  clientId?: string;
  submitLabel: string;
};

/** A quote: title, lines (description, quantity, unit price), deposit, validity and the event. */
export function QuoteForm({ action, defaults, currency, clients, clientId, submitLabel }: Props) {
  const t = useTranslations("quotes");
  const [state, formAction] = useActionState(action, {});
  const [lines, setLines] = useState<Line[]>(() =>
    (defaults.lines.length ? defaults.lines : [{ description: "", quantity: "1", price: "" }]).map((l, i) => ({ ...l, key: i })),
  );
  const [next, setNext] = useState(lines.length);
  const total = lines.reduce((sum, l) => sum + (Number(l.quantity) || 0) * (Number(l.price.replace(",", ".")) || 0), 0);

  const update = (key: number, field: "description" | "quantity" | "price", value: string) =>
    setLines((current) => current.map((l) => (l.key === key ? { ...l, [field]: value } : l)));

  return (
    <form action={formAction} className="flex flex-col gap-5">
      <FormFeedback state={state} />
      {clients && (
        <SelectField
          label={t("client")}
          name="client_id"
          required
          defaultValue={clientId ?? ""}
          options={[{ value: "", label: t("chooseClient") }, ...clients.map((c) => ({ value: c.id, label: c.name }))]}
        />
      )}
      <Field label={t("titleField")} hint={t("titleHint")} name="title" required maxLength={120} dir="auto" defaultValue={defaults.title} />

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1 font-semibold">{t("lines")}</legend>
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
        <Field label={t("deposit")} hint={t("depositHint")} name="deposit_percent" type="number" min={0} max={100} defaultValue={defaults.deposit_percent} />
        <Field label={t("validUntilField")} name="valid_until" type="date" defaultValue={defaults.valid_until} />
        <Field label={t("eventDate")} hint={t("eventHint")} name="event_date" type="date" defaultValue={defaults.event_date} />
        <Field label={t("eventTime")} name="event_time" type="time" defaultValue={defaults.event_time} />
        <div className="sm:col-span-2">
          <Field label={t("eventPlace")} name="event_place" maxLength={200} dir="auto" defaultValue={defaults.event_place} />
        </div>
        <div className="sm:col-span-2">
          <TextAreaField label={t("notes")} placeholder={t("notesHint")} name="notes" rows={4} maxLength={4000} defaultValue={defaults.notes} />
        </div>
      </div>
      <div>
        <SubmitButton>{submitLabel}</SubmitButton>
      </div>
    </form>
  );
}
