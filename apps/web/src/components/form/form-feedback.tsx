"use client";

import { useTranslations } from "next-intl";

import type { FormState } from "@/lib/form-state";

import { FormError, FormNotice } from "./form-message";

export function FormFeedback({ state }: { state: FormState }) {
  const t = useTranslations("common");
  return (
    <>
      <FormError message={state.error && t(`errors.${state.error}`)} />
      <FormNotice message={state.saved ? t("saved") : undefined} />
    </>
  );
}
