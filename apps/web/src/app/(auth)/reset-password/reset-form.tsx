"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { PasswordField } from "@/components/form/password-field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type FormState, updatePassword } from "../actions";

export function ResetForm() {
  const t = useTranslations("auth");
  const [state, action] = useActionState<FormState, FormData>(updatePassword, {});

  const message = state.error ? t(`errors.${state.error}` as "errors.generic") : undefined;
  const onPassword = state.error === "weak_password";

  return (
    <form action={action} className="flex flex-col gap-4">
      <FormError inline message={onPassword ? undefined : message} />
      <PasswordField
        label={t("newPassword")}
        hint={t("passwordHint")}
        name="password"
        autoComplete="new-password"
        minLength={8}
        required
        error={onPassword ? message : undefined}
      />
      <SubmitButton>{t("reset.submit")}</SubmitButton>
    </form>
  );
}
