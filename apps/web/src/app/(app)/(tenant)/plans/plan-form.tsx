"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState, useState } from "react";

import { CheckboxField, Field, SelectField, TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";
import { toMajorUnits } from "@/lib/money";

type Plan = components["schemas"]["Plan"];

type Props = {
  action: (state: FormState, formData: FormData) => Promise<FormState>;
  plan?: Plan;
  currency: string;
  submitLabel: string;
  readOnly?: boolean;
};

export function PlanForm({ action, plan, currency, submitLabel, readOnly = false }: Props) {
  const t = useTranslations();
  const [state, formAction] = useActionState(action, {});
  const [kind, setKind] = useState(plan?.kind ?? "membership");

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <fieldset key={plan?.updated_at ?? "new"} disabled={readOnly} className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Field label={t("plans.name")} name="name" required maxLength={120} defaultValue={plan?.name} />
        </div>
        <SelectField
          label={t("plans.kind")}
          name="kind"
          value={kind}
          onChange={(event) => setKind(event.target.value as Plan["kind"])}
          disabled={!!plan}
          options={(["membership", "punch_card"] as const).map((value) => ({ value, label: t(`plans.kinds.${value}`) }))}
        />
        {kind === "punch_card" ? (
          <Field
            label={t("plans.credits")}
            name="credits"
            type="number"
            min={1}
            max={1000}
            required
            disabled={!!plan}
            defaultValue={plan?.credits ?? 10}
          />
        ) : (
          <p className="self-end pb-2 text-sm text-muted">{t("plans.unlimited")}</p>
        )}
        <Field
          label={t("plans.validity")}
          hint={kind === "punch_card" ? t("plans.validityHintCard") : t("plans.validityHintMembership")}
          name="validity_days"
          type="number"
          min={1}
          max={1095}
          required
          defaultValue={plan?.validity_days ?? (kind === "punch_card" ? 90 : 30)}
        />
        <Field
          label={`${t("plans.price")} (${currency})`}
          name="price"
          inputMode="decimal"
          dir="ltr"
          required
          pattern="\d+([.,]\d{1,2})?"
          defaultValue={plan ? toMajorUnits(plan.price_amount, currency) : ""}
        />
        <div className="sm:col-span-2">
          <TextAreaField label={t("plans.description")} name="description" maxLength={2000} defaultValue={plan?.description ?? ""} />
        </div>
        <CheckboxField label={t("plans.active")} name="active" defaultChecked={plan?.active ?? true} />
      </fieldset>
      {plan && <p className="text-sm text-muted">{t("plans.editNote")}</p>}
      {!readOnly && (
        <div className="flex items-center gap-4">
          <SubmitButton>{submitLabel}</SubmitButton>
          <Link href="/plans" className="text-sm text-muted underline-offset-4 hover:underline">
            {t("common.cancel")}
          </Link>
        </div>
      )}
    </form>
  );
}
