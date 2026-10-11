"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type AnswerState, answerQuote } from "./actions";

/** Accept with a name (a simple acceptance record), or decline. */
export function AnswerForm({ token }: { token: string }) {
  const t = useTranslations("quotes.public");
  const [state, accept] = useActionState<AnswerState, FormData>(answerQuote.bind(null, token, true), {});
  const [declined, decline] = useActionState<AnswerState, FormData>(answerQuote.bind(null, token, false), {});
  const error = state.error ?? declined.error;
  return (
    <div className="flex flex-col gap-4">
      <FormError message={error && t(`errors.${error}`)} />
      <form action={accept} className="flex flex-col gap-3">
        <Field label={t("name")} hint={t("nameHint")} name="name" required maxLength={120} autoComplete="name" dir="auto" />
        <div>
          <SubmitButton>{t("accept")}</SubmitButton>
        </div>
      </form>
      <form action={decline}>
        <button type="submit" className="text-sm text-muted underline-offset-4 hover:underline">
          {t("decline")}
        </button>
      </form>
    </div>
  );
}
