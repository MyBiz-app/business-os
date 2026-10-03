"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type FormState, updatePassword } from "../actions";

export function ResetForm() {
  const t = useTranslations("auth");
  const [state, action] = useActionState<FormState, FormData>(updatePassword, {});

  return (
    <form action={action} className="flex flex-col gap-4">
      <FormError message={state.error && t(`errors.${state.error}` as "errors.generic")} />
      <Field
        label={t("newPassword")}
        hint={t("passwordHint")}
        name="password"
        type="password"
        autoComplete="new-password"
        minLength={8}
        required
      />
      <SubmitButton>{t("reset.submit")}</SubmitButton>
    </form>
  );
}
