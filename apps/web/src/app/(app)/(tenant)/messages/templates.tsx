"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field, TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { saveTemplate } from "./actions";

export function TemplateForm() {
  const t = useTranslations("messaging");
  const [state, action] = useActionState(saveTemplate, {});
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormFeedback state={state} />
      <Field label={t("templateName")} name="name" required maxLength={80} />
      <TextAreaField label={t("text")} name="body" required maxLength={1000} rows={3} />
      <div>
        <SubmitButton>{t("saveTemplate")}</SubmitButton>
      </div>
    </form>
  );
}
