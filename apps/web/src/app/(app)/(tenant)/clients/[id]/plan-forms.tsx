"use client";

import { useTranslations } from "next-intl";
import type { components } from "@business-os/api-client";
import { useActionState } from "react";

import { Field, SelectField } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import type { PlanFormState } from "./plan-actions";
import { Button } from "@/components/ui/button";

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
  const tReceipts = useTranslations("receipts");
  const [state, formAction] = useActionState(action, {});
  return (
    <form action={formAction} className="flex flex-col gap-3">
      <Feedback state={state} savedMessage={t("sold")} />
      {/* A retry of the same submission reuses the key; each new sale gets a new one. */}
      <input type="hidden" name="idempotency_key" value={state.nextKey ?? idempotencyKey} />
      <div className="grid gap-3 sm:grid-cols-2">
        <SelectField label={t("plan")} name="plan_id" required options={plans} />
        <Field label={t("startsOn")} name="starts_on" type="date" defaultValue={today} required />
        <SelectField
          label={t("paymentMethod")}
          name="method"
          options={(["card", "cash", "transfer", "other"] as const).map((method) => ({
            value: method,
            label: tReceipts(`methods.${method}`),
          }))}
        />
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

type Request = components["schemas"]["FreezeRequest"];

/** One waiting request: approve it (all of it, or until a day), or decline it, with a message. */
export function RequestDecision({
  request,
  approve,
  reject,
}: {
  request: Request;
  approve: Action;
  reject: Action;
}) {
  const t = useTranslations("plans");
  const [approveState, approveAction] = useActionState(approve, {});
  const [rejectState, rejectAction] = useActionState(reject, {});
  return (
    <div className="flex flex-col gap-3 pt-2">
      <Feedback state={approveState} savedMessage={t("decided")} />
      <Feedback state={rejectState} savedMessage={t("decided")} />
      <form action={approveAction} className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("approvePartial")} name="approved_ends_on" type="date" min={request.starts_on} max={request.ends_on} />
          <Field label={t("decisionNote")} name="note" maxLength={500} />
        </div>
        <div>
          <SubmitButton>{t("approve")}</SubmitButton>
        </div>
      </form>
      <form action={rejectAction} className="flex flex-wrap items-end gap-3">
        <div className="min-w-48 flex-1">
          <Field label={t("decisionNote")} name="note" maxLength={500} />
        </div>
        <SubmitButton variant="secondary">{t("reject")}</SubmitButton>
      </form>
    </div>
  );
}

/** "The client is back": ends a running freeze (or removes one that has not begun). */
export function EndFreezeButton({ action }: { action: (state: PlanFormState) => Promise<PlanFormState> }) {
  const t = useTranslations("plans");
  const [state, formAction] = useActionState(action, {});
  return (
    <form action={formAction} className="inline-flex flex-col gap-1">
      <Feedback state={state} savedMessage={t("endEarlyDone")} />
      <Button type="submit" variant="quiet" className="text-primary-ink">
        {t("endEarly")}
      </Button>
    </form>
  );
}
