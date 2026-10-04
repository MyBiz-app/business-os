"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { closeDay, type CloseDayState } from "./actions";

export function CloseDayForm({ today }: { today: string }) {
  const t = useTranslations("schedule");
  const [state, action] = useActionState<CloseDayState, FormData>(closeDay, {});
  return (
    <form action={action} className="flex flex-col gap-4">
      <FormError message={state.error && t(`closedErrors.${state.error}`)} />
      <FormNotice message={state.cancelled !== undefined ? t("closedDone", { count: state.cancelled }) : undefined} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("closedDate")} name="day" type="date" min={today} required />
        <Field label={t("closedReason")} hint={t("closedReasonHint")} name="reason" maxLength={120} />
      </div>
      <p className="text-sm text-muted">{t("closedHint")}</p>
      <div>
        <SubmitButton>{t("closeDay")}</SubmitButton>
      </div>
    </form>
  );
}
