"use client";

import { TERM_KEYS } from "@business-os/verticals";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

import { updateTerms } from "./actions";

/** One box per renameable word. The industry's own word is the placeholder, so an empty box
 * visibly means "keep the usual word". */
export function TermsForm({ defaults, current }: { defaults: Record<string, string>; current: Record<string, string> }) {
  const t = useTranslations("settings.terms");
  const [state, action] = useActionState<FormState, FormData>(updateTerms, {});
  return (
    <form action={action} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <div key={JSON.stringify(current)} className="grid gap-4 sm:grid-cols-2">
        {TERM_KEYS.map((key) => (
          <Field key={key} label={t(`words.${key}`)} name={key} defaultValue={current[key] ?? ""} placeholder={defaults[key]} maxLength={60} />
        ))}
      </div>
      <div>
        <SubmitButton>{t("save")}</SubmitButton>
      </div>
    </form>
  );
}
