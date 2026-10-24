"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { PasswordField } from "@/components/form/password-field";
import { SubmitButton } from "@/components/form/submit-button";

import { type FormState, signup } from "../actions";

export function SignupForm({ next, email }: { next?: string; email?: string }) {
  const t = useTranslations("auth");
  const [state, action] = useActionState<FormState, FormData>(signup, {});

  const message = state.error ? t(`errors.${state.error}` as "errors.generic") : undefined;
  const onPassword = state.error === "weak_password";

  return (
    <form action={action} className="flex flex-col gap-4">
      {next && <input type="hidden" name="next" value={next} />}
      <FormError inline message={onPassword ? undefined : message} />
      <Field label={t("email")} name="email" type="email" autoComplete="email" required defaultValue={state.email ?? email} />
      <PasswordField
        label={t("password")}
        hint={t("passwordHint")}
        name="password"
        autoComplete="new-password"
        minLength={8}
        required
        error={onPassword ? message : undefined}
      />
      <SubmitButton>{t("signup.submit")}</SubmitButton>
    </form>
  );
}
