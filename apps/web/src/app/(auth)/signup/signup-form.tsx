"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type FormState, signup } from "../actions";

export function SignupForm() {
  const t = useTranslations("auth");
  const [state, action] = useActionState<FormState, FormData>(signup, {});

  return (
    <form action={action} className="flex flex-col gap-4">
      <FormError message={state.error && t(`errors.${state.error}` as "errors.generic")} />
      <Field label={t("email")} name="email" type="email" autoComplete="email" required defaultValue={state.email} />
      <Field
        label={t("password")}
        hint={t("passwordHint")}
        name="password"
        type="password"
        autoComplete="new-password"
        minLength={8}
        required
      />
      <SubmitButton>{t("signup.submit")}</SubmitButton>
    </form>
  );
}
