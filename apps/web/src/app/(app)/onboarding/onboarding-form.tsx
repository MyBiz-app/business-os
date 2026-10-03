"use client";

import { useLocale, useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field, SelectField } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { locales } from "@/i18n/config";

import { createBusiness, type OnboardingState } from "./actions";

const VERTICALS = ["fitness"] as const;
const CURRENCIES = ["ILS", "USD", "EUR"] as const;

export function OnboardingForm({ timeZones }: { timeZones: string[] }) {
  const t = useTranslations();
  const locale = useLocale();
  const [state, action] = useActionState<OnboardingState, FormData>(createBusiness, {});
  const israel = locale === "he";

  return (
    <form action={action} className="flex flex-col gap-4">
      <FormError
        message={state.error && (state.error === "invalid" ? t("onboarding.errors.invalid") : t("auth.errors.generic"))}
      />
      <Field label={t("onboarding.name")} name="name" required maxLength={120} autoComplete="organization" />
      <SelectField
        label={t("onboarding.vertical")}
        name="vertical"
        options={VERTICALS.map((value) => ({ value, label: t(`onboarding.verticals.${value}`) }))}
      />
      <SelectField
        label={t("onboarding.locale")}
        name="locale"
        defaultValue={locale}
        options={locales.map((value) => ({ value, label: t(`locales.${value}`) }))}
      />
      <SelectField
        label={t("onboarding.timeZone")}
        name="time_zone"
        defaultValue={israel ? "Asia/Jerusalem" : "America/New_York"}
        dir="ltr"
        options={timeZones.map((value) => ({ value, label: value.replaceAll("_", " ") }))}
      />
      <SelectField
        label={t("onboarding.currency")}
        name="currency"
        defaultValue={israel ? "ILS" : "USD"}
        options={CURRENCIES.map((value) => ({ value, label: t(`onboarding.currencies.${value}`) }))}
      />
      <SubmitButton>{t("onboarding.submit")}</SubmitButton>
    </form>
  );
}
