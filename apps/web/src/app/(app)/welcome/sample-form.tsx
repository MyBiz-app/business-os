"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { SelectField } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { industryOptions, industryTexts } from "@/lib/verticals";

import { exploreSample, type SampleState } from "./actions";

export function SampleForm() {
  const t = useTranslations();
  const { text } = industryTexts(t);
  const [state, action] = useActionState<SampleState, FormData>(exploreSample, {});
  return (
    <form action={action} className="mt-auto flex flex-col gap-3">
      <FormError message={state.error ? t("welcome.sample.error") : undefined} />
      <SelectField
        label={t("welcome.sample.industry")}
        name="vertical"
        options={industryOptions(text, (name) => t("start.industry.otherKind", { name }))}
      />
      <SubmitButton>
        {t("welcome.sample.button")}
      </SubmitButton>
    </form>
  );
}
