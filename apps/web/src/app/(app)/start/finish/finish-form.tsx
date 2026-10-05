"use client";

import { CreditCard } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useSyncExternalStore } from "react";

import { Field } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type FinishState, startTrial } from "./actions";

const noSubscribe = () => () => {};
const browserZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;
const serverZone = () => "";

/** The card for after the trial. Payments are simulated until a provider is connected, so the
 * test card is filled in and nothing is charged. */
export function FinishForm({ plan }: { plan: string }) {
  const t = useTranslations("start.finish");
  const [state, action] = useActionState<FinishState, FormData>(startTrial, {});
  const timeZone = useSyncExternalStore(noSubscribe, browserZone, serverZone);

  return (
    <form action={action} className="card flex flex-col gap-4 p-6">
      <input type="hidden" name="plan" value={plan} />
      <input type="hidden" name="time_zone" value={timeZone} />
      <input type="hidden" name="brand" value="visa" />
      <FormError message={state.error && t(`errors.${state.error}`)} />
      <p role="note" className="flex items-start gap-2 rounded-xl bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-800 dark:text-amber-300">
        <CreditCard aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        {t("simulated")}
      </p>
      <Field label={t("card")} name="card" defaultValue="4242 4242 4242 4242" dir="ltr" inputMode="numeric" autoComplete="cc-number" readOnly />
      <div className="grid grid-cols-2 gap-4">
        <Field label={t("expiry")} name="expiry" defaultValue="12/30" dir="ltr" autoComplete="cc-exp" readOnly />
        <Field label={t("cvc")} name="cvc" defaultValue="123" dir="ltr" autoComplete="cc-csc" readOnly />
      </div>
      <Field label={t("holder")} name="holder" autoComplete="cc-name" />
      <SubmitButton>{t("submit")}</SubmitButton>
    </form>
  );
}
