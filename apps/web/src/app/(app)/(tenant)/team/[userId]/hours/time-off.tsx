"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { addTimeOff } from "./actions";

export function TimeOffForm({ userId, today }: { userId: string; today: string }) {
  const t = useTranslations("timeOff");
  const [state, action] = useActionState(addTimeOff.bind(null, userId), {});
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormFeedback state={state} />
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t("from")} name="starts_on" type="date" required min={today} />
        <Field label={t("to")} name="ends_on" type="date" min={today} hint={t("toHint")} />
        <Field label={t("reason")} name="reason" maxLength={200} />
      </div>
      <div>
        <SubmitButton>{t("add")}</SubmitButton>
      </div>
    </form>
  );
}
