"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { CODE_LENGTH } from "@/lib/mfa";

import { type FormState, verifyMfa } from "../../actions";

export function MfaForm({ next }: { next?: string }) {
  const t = useTranslations("security");
  const [state, action] = useActionState<FormState, FormData>(verifyMfa, {});

  return (
    <form action={action} className="flex flex-col gap-4">
      {next && <input type="hidden" name="next" value={next} />}
      <FormError message={state.error && t(`errors.${state.error}` as "errors.generic")} />
      <Field
        label={t("mfa.code")}
        name="code"
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern={`\\d{${CODE_LENGTH}}`}
        maxLength={CODE_LENGTH}
        dir="ltr"
        required
        autoFocus
      />
      <SubmitButton>{t("challenge.submit")}</SubmitButton>
    </form>
  );
}
