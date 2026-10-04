"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState } from "react";

import { Field, SelectField, TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

import { SOURCES } from "./sources";

type Lead = components["schemas"]["Lead"];
type Owner = components["schemas"]["LeadOwner"];


type Props = {
  action: (state: FormState, formData: FormData) => Promise<FormState>;
  owners: Owner[];
  lead?: Lead;
  submitLabel: string;
  readOnly?: boolean;
};

export function LeadForm({ action, owners, lead, submitLabel, readOnly = false }: Props) {
  const t = useTranslations("leads");
  const [state, formAction] = useActionState(action, {});

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      {/* Keyed by the saved version so the fields show the stored values after a save. */}
      <fieldset key={lead?.updated_at ?? "new"} disabled={readOnly} className="grid gap-4 sm:grid-cols-2">
        <Field label={t("firstName")} name="first_name" required maxLength={100} defaultValue={lead?.first_name} />
        <Field label={t("lastName")} name="last_name" maxLength={100} defaultValue={lead?.last_name ?? ""} />
        <Field label={t("phone")} name="phone" type="tel" maxLength={30} dir="ltr" defaultValue={lead?.phone ?? ""} />
        <Field label={t("email")} name="email" type="email" dir="ltr" defaultValue={lead?.email ?? ""} />
        <SelectField
          label={t("source")}
          name="source"
          defaultValue={lead?.source ?? "manual"}
          options={SOURCES.map((value) => ({ value, label: t(`sources.${value}`) }))}
        />
        <Field label={t("campaign")} name="campaign" maxLength={100} defaultValue={lead?.campaign ?? ""} />
        <SelectField
          label={t("owner")}
          name="owner_user_id"
          defaultValue={lead?.owner_user_id ?? ""}
          options={[
            { value: "", label: t("noOwner") },
            ...owners.map((o) => ({ value: o.user_id, label: o.name })),
          ]}
        />
        <Field label={t("followUp")} name="follow_up_on" type="date" defaultValue={lead?.follow_up_on ?? ""} />
        <div className="sm:col-span-2">
          <TextAreaField label={t("interest")} name="interest" maxLength={2000} rows={3} defaultValue={lead?.interest ?? ""} />
        </div>
      </fieldset>
      {!readOnly && (
        <div className="flex items-center gap-4">
          <SubmitButton>{submitLabel}</SubmitButton>
          {!lead && (
            <Link href="/leads" className="text-sm text-muted underline-offset-4 hover:underline">
              {t("cancel")}
            </Link>
          )}
        </div>
      )}
    </form>
  );
}
