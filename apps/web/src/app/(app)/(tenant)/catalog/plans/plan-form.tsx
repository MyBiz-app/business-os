"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { CheckboxField, Field, SelectField, TextAreaField } from "@/components/form/field";
import type { FormState } from "@/lib/form-state";
import { toMajorUnits } from "@/lib/money";

import { CatalogFormFrame } from "../form-frame";

type Plan = components["schemas"]["Plan"];

type Props = {
  action: (state: FormState, formData: FormData) => Promise<FormState>;
  plan?: Plan;
  currency: string;
  submitLabel: string;
  readOnly?: boolean;
  /** Shown as a window over the list instead of a page. */
  modal?: boolean;
  /** The delete button, under the fields. */
  aside?: React.ReactNode;
};

export function PlanForm({ action, plan, currency, submitLabel, readOnly = false, modal = false, aside }: Props) {
  const t = useTranslations();
  const [state, formAction] = useActionState(action, {});
  const [kind, setKind] = useState(plan?.kind ?? "membership");
  const [cycle, setCycle] = useState<string>(plan?.billing_cycle ?? "");
  const [periodUnit, setPeriodUnit] = useState<string>(plan?.period_unit ?? "");

  return (
    <CatalogFormFrame
      modal={modal}
      backHref="/catalog?tab=plans"
      formAction={formAction}
      state={state}
      savedMessage={plan ? t("common.saved") : t("plans.created")}
      closeOnSave={modal || !plan}
      readOnly={readOnly}
      submitLabel={submitLabel}
      aside={aside}
    >
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
      {kind === "membership" && (
        <SelectField
          label={t("plans.cycle")}
          name="billing_cycle"
          value={cycle}
          onChange={(event) => setCycle(event.target.value)}
          disabled={!!plan}
          options={[
            { value: "", label: t("plans.cycles.none") },
            ...(["monthly", "quarterly", "yearly", "custom"] as const).map((value) => ({ value, label: t(`plans.cycles.${value}`) })),
          ]}
        />
      )}
      {kind === "membership" && cycle === "custom" && (
        <Field
          label={t("plans.cycleDays")}
          name="billing_cycle_days"
          type="number"
          min={1}
          max={1095}
          required
          disabled={!!plan}
          defaultValue={plan?.billing_cycle_days ?? 30}
        />
      )}
      {kind === "membership" && cycle !== "" ? (
        <>
          {plan && <input type="hidden" name="auto_renew_shown" value="1" />}
          <div className="sm:col-span-2">
            <CheckboxField label={t("plans.autoRenew")} name="auto_renew" defaultChecked={plan?.auto_renew ?? true} />
            <p className="text-xs text-muted">{t("plans.autoRenewHint")}</p>
          </div>
        </>
      ) : (
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
      )}
      {kind === "membership" && (
        <>
          <SelectField
            label={t("plans.quota")}
            name="period_unit"
            value={periodUnit}
            onChange={(event) => setPeriodUnit(event.target.value)}
            options={[
              { value: "", label: t("plans.quotas.none") },
              ...(["week", "month"] as const).map((value) => ({ value, label: t(`plans.quotas.${value}`) })),
            ]}
          />
          {periodUnit !== "" ? (
            <Field label={t("plans.quotaVisits")} name="period_quota" type="number" min={1} max={100} required defaultValue={plan?.period_quota ?? 2} />
          ) : (
            <p className="self-end pb-2 text-xs text-muted">{t("plans.quotaHint")}</p>
          )}
        </>
      )}
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
    </CatalogFormFrame>
  );
}
