"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type FormState, requestPasswordReset } from "../actions";

export function ForgotForm() {
  const t = useTranslations("auth");
  const [state, action] = useActionState<FormState, FormData>(requestPasswordReset, {});

  return (
    <form action={action} className="flex flex-col gap-4">
      <FormError message={state.error && t(`errors.${state.error}` as "errors.generic")} />
      <FormNotice message={state.notice && t("forgot.sent")} />
      <Field label={t("email")} name="email" type="email" autoComplete="email" required defaultValue={state.email} />
      <SubmitButton>{t("forgot.submit")}</SubmitButton>
    </form>
  );
}
