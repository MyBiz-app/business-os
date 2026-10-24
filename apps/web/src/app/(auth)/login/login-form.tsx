"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { PasswordField } from "@/components/form/password-field";
import { SubmitButton } from "@/components/form/submit-button";

import { type FormState, login } from "../actions";

export function LoginForm({ initialError, next }: { initialError?: string; next?: string }) {
  const t = useTranslations("auth");
  const [state, action] = useActionState<FormState, FormData>(login, { error: initialError });

  const message = state.error ? t(`errors.${state.error}` as "errors.generic") : undefined;
  const onPassword = state.error === "invalid_credentials";

  return (
    <form action={action} className="flex flex-col gap-4">
      {next && <input type="hidden" name="next" value={next} />}
      <FormError inline message={onPassword ? undefined : message} />
      <Field label={t("email")} name="email" type="email" autoComplete="email" required defaultValue={state.email} />
      <PasswordField label={t("password")} name="password" autoComplete="current-password" required error={onPassword ? message : undefined} />
      <Link href="/forgot-password" className="text-sm text-primary-ink underline-offset-4 hover:underline">
        {t("login.forgot")}
      </Link>
      <SubmitButton>{t("login.submit")}</SubmitButton>
    </form>
  );
}
