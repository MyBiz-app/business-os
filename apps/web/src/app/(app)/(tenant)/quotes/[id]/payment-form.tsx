"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field, SelectField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { recordQuotePayment } from "../actions";

/** Staff record a payment for an accepted quote (the deposit or the balance). */
export function PaymentForm({ quoteId, paymentKey, due, currency }: { quoteId: string; paymentKey: string; due: string; currency: string }) {
  const t = useTranslations("quotes");
  const tMethods = useTranslations("resources.methods");
  const [state, action] = useActionState(recordQuotePayment.bind(null, quoteId, paymentKey), {});
  return (
    <form action={action} className="flex flex-wrap items-end gap-3">
      <FormFeedback state={state} />
      <Field label={`${t("amount")} (${currency})`} name="amount" inputMode="decimal" dir="ltr" required pattern="\d+([.,]\d{1,2})?" defaultValue={due} />
      <SelectField
        label={t("method")}
        name="method"
        defaultValue="transfer"
        options={(["cash", "card", "transfer", "other"] as const).map((m) => ({ value: m, label: tMethods(m) }))}
      />
      <SubmitButton>{t("recordPayment")}</SubmitButton>
    </form>
  );
}
