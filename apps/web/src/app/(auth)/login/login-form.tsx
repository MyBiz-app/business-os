"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type FormState, login } from "../actions";

export function LoginForm({ initialError }: { initialError?: string }) {
  const t = useTranslations("auth");
  const [state, action] = useActionState<FormState, FormData>(login, { error: initialError });

  return (
    <form action={action} className="flex flex-col gap-4">
      <FormError message={state.error && t(`errors.${state.error}` as "errors.generic")} />
      <Field label={t("email")} name="email" type="email" autoComplete="email" required defaultValue={state.email} />
      <Field label={t("password")} name="password" type="password" autoComplete="current-password" required />
      <Link href="/forgot-password" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("login.forgot")}
      </Link>
      <SubmitButton>{t("login.submit")}</SubmitButton>
    </form>
  );
}
