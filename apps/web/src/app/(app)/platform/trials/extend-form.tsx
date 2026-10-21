"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useActionState } from "react";

import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { extendFromList, type TrialState } from "./actions";

/** A small inline form: extend one business's trial by a number of days. */
export function ExtendForm({ tenantId }: { tenantId: string }) {
  const t = useTranslations("platform.trials");
  const tCard = useTranslations("platform.card.errors");
  const format = useFormatter();
  const [state, action] = useActionState<TrialState, FormData>(extendFromList.bind(null, tenantId), {});
  return (
    <form action={action} className="flex flex-wrap items-end gap-2">
      <label className="flex flex-col gap-1 text-xs">
        <span className="text-muted">{t("extendDays")}</span>
        <input name="days" type="number" min={1} max={180} defaultValue={7} className="control w-20 px-2 py-1.5" />
      </label>
      <SubmitButton variant="secondary" className="px-3 py-1.5 text-sm">
        {t("extend")}
      </SubmitButton>
      <FormError message={state.error ? tCard(state.error as "generic") : undefined} />
      <FormNotice message={state.done ? t("extendDone", { date: format.dateTime(new Date(state.done), { dateStyle: "medium" }) }) : undefined} />
    </form>
  );
}
