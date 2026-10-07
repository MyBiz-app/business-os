"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { CheckboxField, Field, SelectField } from "@/components/form/field";
import { FileField } from "@/components/form/file-field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { type BillState, billMonth, logTime, saveRetainer, uploadDocument } from "./work-actions";

export function DocumentForm({ clientId }: { clientId: string }) {
  const t = useTranslations("documents");
  const [state, action] = useActionState(uploadDocument.bind(null, clientId), {});
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormFeedback state={state} />
      <FileField label={t("file")} hint={t("fileHint")} name="file" required accept=".pdf,.png,.jpg,.jpeg,.webp,.doc,.docx,.xls,.xlsx,.csv,.txt" />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("name")} name="name" maxLength={200} dir="auto" />
        <SelectField
          label={t("kind")}
          name="kind"
          defaultValue="other"
          options={(["contract", "report", "other"] as const).map((k) => ({ value: k, label: t(`kinds.${k}`) }))}
        />
      </div>
      <CheckboxField label={t("shareWithClient")} name="shared" />
      <CheckboxField label={t("askToSign")} name="sign_requested" />
      <div>
        <SubmitButton>{t("upload")}</SubmitButton>
      </div>
    </form>
  );
}

export function TimeForm({ clientId, today }: { clientId: string; today: string }) {
  const t = useTranslations("time");
  const [state, action] = useActionState(logTime.bind(null, clientId), {});
  return (
    <form action={action} className="flex flex-col gap-3 rounded-xl bg-foreground/[0.03] p-3">
      <FormFeedback state={state} />
      <div className="grid gap-3 sm:grid-cols-[9rem_7rem_1fr]">
        <Field label={t("day")} name="day" type="date" required defaultValue={today} />
        <Field label={t("hours")} name="hours" inputMode="decimal" dir="ltr" required pattern="\d+([.,]\d{1,2})?" placeholder="1.5" />
        <Field label={t("what")} name="description" required maxLength={500} dir="auto" />
      </div>
      <CheckboxField label={t("billable")} name="billable" defaultChecked />
      <div>
        <SubmitButton>{t("log")}</SubmitButton>
      </div>
    </form>
  );
}

type RetainerValues = { monthly: string; included_hours: string; rate: string };

export function RetainerForm({ clientId, values, currency }: { clientId: string; values: RetainerValues; currency: string }) {
  const t = useTranslations("time.retainer");
  const [state, action] = useActionState(saveRetainer.bind(null, clientId), {});
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormFeedback state={state} />
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={`${t("monthly")} (${currency})`} hint={t("monthlyHint")} name="monthly" inputMode="decimal" dir="ltr" pattern="\d+([.,]\d{1,2})?" defaultValue={values.monthly} />
        <Field label={t("included")} name="included_hours" inputMode="decimal" dir="ltr" defaultValue={values.included_hours} />
        <Field label={`${t("rate")} (${currency})`} name="rate" inputMode="decimal" dir="ltr" pattern="\d+([.,]\d{1,2})?" defaultValue={values.rate} />
      </div>
      <div>
        <SubmitButton>{t("save")}</SubmitButton>
      </div>
    </form>
  );
}

export function BillForm({ clientId, months }: { clientId: string; months: { value: string; label: string }[] }) {
  const t = useTranslations("time");
  const [state, action] = useActionState<BillState, FormData>(billMonth.bind(null, clientId), {});
  return (
    <form action={action} className="flex flex-wrap items-end gap-3">
      <SelectField label={t("month")} name="month" defaultValue={months[0]?.value} options={months} />
      <SubmitButton>{t("bill")}</SubmitButton>
      {state.nothing && <p role="status" className="w-full text-sm text-muted">{t("nothingToBill")}</p>}
      {state.error && <p role="alert" className="w-full text-sm text-danger">{t("billFailed")}</p>}
    </form>
  );
}
