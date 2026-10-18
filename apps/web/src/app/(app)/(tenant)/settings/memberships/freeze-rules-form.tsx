"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { CheckboxField, Field, SelectField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";
import { toMajorUnits } from "@/lib/money";

import { saveFreezeRules } from "./actions";

type Rules = components["schemas"]["FreezeRules"];

const REASONS = ["travel", "reserve_duty", "illness", "pregnancy", "other"] as const;

export function FreezeRulesForm({ rules, currency }: { rules: Rules; currency: string }) {
  const t = useTranslations();
  const [state, action] = useActionState<FormState, FormData>(saveFreezeRules, {});
  return (
    <form action={action} className="flex flex-col gap-4 card p-6">
      <FormFeedback state={state} />
      <p className="text-sm text-muted">{t("settings.freezeRules.intro")}</p>
      <CheckboxField label={t("settings.freezeRules.allow")} name="allow_requests" defaultChecked={rules.allow_requests} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("settings.freezeRules.minDays")} name="min_days" type="number" min={1} max={90} required defaultValue={rules.min_days} />
        <Field label={t("settings.freezeRules.maxDays")} name="max_days" type="number" min={1} max={90} required defaultValue={rules.max_days} />
        <Field
          label={t("settings.freezeRules.bank")}
          hint={t("settings.freezeRules.bankHint")}
          name="yearly_bank_days"
          type="number"
          min={1}
          max={366}
          defaultValue={rules.yearly_bank_days ?? ""}
        />
        <Field label={t("settings.freezeRules.notice")} name="notice_days" type="number" min={0} max={60} defaultValue={rules.notice_days} />
        <Field
          label={`${t("settings.freezeRules.fee")} (${currency})`}
          hint={t("settings.freezeRules.feeHint")}
          name="fee"
          inputMode="decimal"
          dir="ltr"
          pattern="\d+([.,]\d{1,2})?"
          defaultValue={toMajorUnits(rules.fee_amount, currency)}
        />
        <div className="flex flex-col gap-1">
          <SelectField
            label={t("settings.freezeRules.billingMode")}
            name="billing_mode"
            defaultValue={rules.billing_mode}
            options={(["defer", "credit"] as const).map((value) => ({ value, label: t(`settings.freezeRules.billingModes.${value}`) }))}
          />
          <p className="text-xs text-muted">{t("settings.freezeRules.billingHint")}</p>
        </div>
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-medium">{t("settings.freezeRules.autoApprove")}</legend>
        <p className="text-xs text-muted">{t("settings.freezeRules.autoApproveHint")}</p>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {REASONS.map((reason) => (
            <CheckboxField
              key={reason}
              label={t(`freeze.reasons.${reason}`)}
              name={`auto_${reason}`}
              defaultChecked={(rules.auto_approve_reasons ?? []).includes(reason)}
            />
          ))}
        </div>
      </fieldset>
      <div>
        <SubmitButton>{t("settings.freezeRules.save")}</SubmitButton>
      </div>
    </form>
  );
}
