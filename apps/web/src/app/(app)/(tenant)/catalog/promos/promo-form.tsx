"use client";

import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { Field, SelectField } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";

import { CatalogFormFrame } from "../form-frame";
import { createPromoCode, type PromoState } from "./actions";

type Props = { plans: { id: string; name: string }[]; currencySymbol: string; modal?: boolean };

/** A new discount code, as a window over the list or as a page. */
export function PromoForm({ plans, currencySymbol, modal = false }: Props) {
  const t = useTranslations("promo");
  const [state, action] = useActionState<PromoState, FormData>(createPromoCode, {});
  const [kind, setKind] = useState<"percent" | "amount">("percent");
  return (
    <CatalogFormFrame
      modal={modal}
      title={t("new")}
      backHref="/catalog?tab=codes"
      formAction={action}
      state={{ saved: state.saved }}
      savedMessage={t("created")}
      closeOnSave
      submitLabel={t("create")}
    >
      <FormError message={state.error && t(`errors.${state.error}`)} />
      <div className="grid gap-4 sm:grid-cols-2">
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
    </CatalogFormFrame>
  );
}
