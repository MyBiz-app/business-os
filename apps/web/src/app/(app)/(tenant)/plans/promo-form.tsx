"use client";

import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { Field, SelectField } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { createPromoCode, type PromoState } from "./promo-actions";

type Props = { plans: { id: string; name: string }[]; currencySymbol: string };

export function PromoForm({ plans, currencySymbol }: Props) {
  const t = useTranslations("promo");
  const [state, action] = useActionState<PromoState, FormData>(createPromoCode, {});
  const [kind, setKind] = useState<"percent" | "amount">("percent");
  return (
    <form action={action} className="flex flex-col gap-4">
      <FormError message={state.error && t(`errors.${state.error}`)} />
      <FormNotice message={state.saved ? t("created") : undefined} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Field
          label={t("code")}
          name="code"
          required
          pattern="[A-Za-z0-9_\-]{3,20}"
          maxLength={20}
          dir="ltr"
          hint={t("codeHint")}
          className="control w-full min-w-0 px-3 py-2 uppercase"
        />
        <SelectField
          label={t("kind")}
          name="kind"
          value={kind}
          onChange={(event) => setKind(event.target.value as "percent" | "amount")}
          options={[
            { value: "percent", label: t("percent") },
            { value: "amount", label: t("amount") },
          ]}
        />
        <Field
          label={kind === "percent" ? t("percentValue") : t("amountValue", { currency: currencySymbol })}
          name="value"
          required
          inputMode="decimal"
          dir="ltr"
        />
        <SelectField
          label={t("plan")}
          name="plan_id"
          defaultValue=""
          options={[{ value: "", label: t("allPlans") }, ...plans.map((p) => ({ value: p.id, label: p.name }))]}
        />
        <Field label={t("startsOn")} name="starts_on" type="date" />
        <Field label={t("endsOn")} name="ends_on" type="date" />
        <Field label={t("maxUses")} name="max_uses" type="number" min={1} hint={t("maxUsesHint")} />
      </div>
      <div>
        <SubmitButton>{t("create")}</SubmitButton>
      </div>
    </form>
  );
}
