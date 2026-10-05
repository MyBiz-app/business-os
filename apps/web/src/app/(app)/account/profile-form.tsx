"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

import { saveProfile } from "./actions";

export function ProfileForm({ name, email }: { name: string | null; email: string }) {
  const t = useTranslations();
  const [state, action] = useActionState<FormState, FormData>(saveProfile, {});
  return (
    <form action={action} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <Field label={t("account.name")} hint={t("account.nameHint")} name="full_name" defaultValue={name ?? ""} maxLength={120} autoComplete="name" dir="auto" />
      <Field label={t("account.email")} hint={t("account.emailHint")} value={email} readOnly dir="ltr" />
      <div>
        <SubmitButton>{t("common.save")}</SubmitButton>
      </div>
    </form>
  );
}
