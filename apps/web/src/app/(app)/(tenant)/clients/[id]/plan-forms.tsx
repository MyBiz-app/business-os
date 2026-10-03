"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field, SelectField } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import type { PlanFormState } from "./plan-actions";

type Action = (state: PlanFormState, formData: FormData) => Promise<PlanFormState>;

function Feedback({ state, savedMessage }: { state: PlanFormState; savedMessage: string }) {
  const t = useTranslations("plans.errors");
  return (
    <>
      <FormError message={state.error && t(state.error)} />
      <FormNotice message={state.saved ? savedMessage : undefined} />
    </>
  );
}

type SellProps = {
  action: Action;
  plans: { value: string; label: string }[];
  today: string;
  idempotencyKey: string;
};

export function SellPlanForm({ action, plans, today, idempotencyKey }: SellProps) {
  const t = useTranslations("plans");
  const [state, formAction] = useActionState(action, {});
  return (
    <form action={formAction} className="flex flex-col gap-3">
      <Feedback state={state} savedMessage={t("sold")} />
      {/* A retry of the same submission reuses the key; each new sale gets a new one. */}
      <input type="hidden" name="idempotency_key" value={state.nextKey ?? idempotencyKey} />
      <div className="grid gap-3 sm:grid-cols-2">
        <SelectField label={t("plan")} name="plan_id" required options={plans} />
        <Field label={t("startsOn")} name="starts_on" type="date" defaultValue={today} required />
      </div>
      <p className="text-xs text-muted">{t("simulatedPayment")}</p>
      <div>
        <SubmitButton>{t("sell")}</SubmitButton>
      </div>
    </form>
  );
}

export function FreezeForm({ action, today }: { action: Action; today: string }) {
  const t = useTranslations("plans");
  const [state, formAction] = useActionState(action, {});
  return (
    <form action={formAction} className="flex flex-col gap-3 pt-3">
      <Feedback state={state} savedMessage={t("frozen")} />
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t("freezeFrom")} name="starts_on" type="date" defaultValue={today} required />
        <Field label={t("freezeTo")} name="ends_on" type="date" required />
        <Field label={t("freezeReason")} name="reason" maxLength={500} />
      </div>
      <div>
        <SubmitButton>{t("freeze")}</SubmitButton>
      </div>
    </form>
  );
}
