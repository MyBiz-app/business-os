"use client";

import { useLocale, useTranslations } from "next-intl";
import { useActionState, useRef, useState } from "react";

import { CheckboxField, Field, SelectField } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { type Catalog, ModulePicker, type Selection } from "@/components/modules/module-picker";
import { locales } from "@/i18n/config";

import { createBusiness, type OnboardingState, recommendModules } from "./actions";

const VERTICALS = ["fitness", "beauty", "clinic", "garage"] as const;
const CURRENCIES = ["ILS", "USD", "EUR"] as const;

type Props = { timeZones: string[]; catalogs: Record<string, Catalog> };

/** Step 1: the business and a few questions. Step 2: the recommended modules, adjustable,
 * with a live price. Both steps are one form, submitted once at the end. */
export function OnboardingForm({ timeZones, catalogs }: Props) {
  const t = useTranslations();
  const locale = useLocale();
  const [state, action] = useActionState<OnboardingState, FormData>(createBusiness, {});
  const israel = locale === "he";
  const form = useRef<HTMLFormElement>(null);
  const [currency, setCurrency] = useState(israel ? "ILS" : "USD");
  const [step, setStep] = useState<1 | 2>(1);
  const [recommended, setRecommended] = useState<Selection>({});
  const [activeClients, setActiveClients] = useState(0);
  const [busy, setBusy] = useState(false);

  const next = async () => {
    const current = form.current;
    if (!current?.reportValidity()) return;
    const data = new FormData(current);
    const number = (key: string, fallback: number) => Math.max(fallback, Number(data.get(key)) || fallback);
    const answers = {
      active_clients: number("q_clients", 0),
      staff: number("q_staff", 1),
      locations: number("q_locations", 1),
      wants_client_app: data.get("q_app") === "on",
      wants_ai_actions: data.get("q_ai") === "on",
    };
    setBusy(true);
    try {
      setRecommended(await recommendModules(answers));
    } finally {
      setBusy(false);
    }
    setActiveClients(answers.active_clients);
    setStep(2);
  };

  return (
    <form ref={form} action={action} className="flex flex-col gap-4">
      <FormError
        message={state.error && (state.error === "invalid" ? t("onboarding.errors.invalid") : t("auth.errors.generic"))}
      />
      <p className="text-sm font-medium text-muted" aria-live="polite">
        {t("onboarding.step", { step, total: 2 })}
      </p>

      <div className={step === 1 ? "flex flex-col gap-4" : "hidden"}>
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
          value={currency}
          onChange={(event) => setCurrency(event.target.value)}
          options={CURRENCIES.map((value) => ({ value, label: t(`onboarding.currencies.${value}`) }))}
        />

        <fieldset className="flex flex-col gap-4 border-t border-border pt-4">
          <legend className="pt-4 font-semibold">{t("onboarding.questions")}</legend>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t("onboarding.qClients")} name="q_clients" type="number" min={0} defaultValue={50} />
            <Field label={t("onboarding.qStaff")} name="q_staff" type="number" min={1} defaultValue={2} />
            <Field label={t("onboarding.qLocations")} name="q_locations" type="number" min={1} defaultValue={1} />
          </div>
          <CheckboxField label={t("onboarding.qApp")} name="q_app" defaultChecked />
          <CheckboxField label={t("onboarding.qAi")} name="q_ai" />
        </fieldset>
        <button
          type="button"
          onClick={() => void next()}
          disabled={busy}
          className="btn-primary px-4 py-2.5"
        >
          {t("onboarding.next")}
        </button>
      </div>

      {step === 2 && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <h2 className="text-lg font-semibold">{t("onboarding.planTitle")}</h2>
            <p className="text-sm text-muted">{t("onboarding.planHint")}</p>
          </div>
          <ModulePicker
            key={JSON.stringify(recommended) + currency}
            catalog={catalogs[currency]}
            initial={recommended}
            activeClients={activeClients}
            name="modules"
          />
          <div className="flex items-center gap-4">
            <SubmitButton>{t("onboarding.submit")}</SubmitButton>
            <button type="button" onClick={() => setStep(1)} className="text-sm text-muted underline-offset-4 hover:underline">
              {t("onboarding.back")}
            </button>
          </div>
        </div>
      )}
    </form>
  );
}
