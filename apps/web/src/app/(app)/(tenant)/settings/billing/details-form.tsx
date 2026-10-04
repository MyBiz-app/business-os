"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { saveDetails } from "./actions";

type Details = components["schemas"]["BillingDetails"];

export function DetailsForm({ details }: { details: Details }) {
  const t = useTranslations("billing");
  const [state, action] = useActionState(saveDetails, {});
  return (
    <form action={action} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label={t("billingName")} name="billing_name" maxLength={160} defaultValue={details.billing_name ?? ""} />
        <Field label={t("billingEmail")} name="billing_email" type="email" dir="ltr" defaultValue={details.billing_email ?? ""} />
        <Field label={t("taxId")} name="tax_id" maxLength={40} dir="ltr" defaultValue={details.tax_id ?? ""} />
      </div>
      <div>
        <SubmitButton>{t("saveDetails")}</SubmitButton>
      </div>
    </form>
  );
}
