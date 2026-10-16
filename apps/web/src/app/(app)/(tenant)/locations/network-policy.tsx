"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { CheckboxField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

type Props = {
  action: (state: FormState, formData: FormData) => Promise<FormState>;
  scope: "network" | "branch";
  /** With a single branch the policy changes nothing yet, so no warning is shown. */
  multiBranch: boolean;
};

export function NetworkPolicy({ action, scope, multiBranch }: Props) {
  const t = useTranslations("locations.network");
  const [state, formAction] = useActionState(action, {});
  const options = ["network", "branch"] as const;

  return (
    <form action={formAction} className="card flex flex-col gap-4 p-5" aria-labelledby="network-policy-heading">
      <div className="flex flex-col gap-1">
        <h2 id="network-policy-heading" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted">{t("hint")}</p>
      </div>
      <FormFeedback state={state} />
      <fieldset key={scope} className="flex flex-col gap-3 sm:flex-row">
        <legend className="sr-only">{t("title")}</legend>
        {options.map((option) => (
          <label key={option} className="flex flex-1 cursor-pointer items-start gap-3 rounded-xl border border-border p-3 has-[:checked]:border-primary has-[:checked]:bg-primary/5">
            <input type="radio" name="network_scope" value={option} defaultChecked={scope === option} className="mt-1" />
            <span className="flex flex-col gap-0.5">
              <span className="font-medium">{t(option)}</span>
              <span className="text-xs text-muted">{t(`${option}Hint`)}</span>
            </span>
          </label>
        ))}
      </fieldset>
      {multiBranch && (
        <>
          <p className="rounded-xl bg-warning/10 p-3 text-sm" role="note">
            {t("warning")}
          </p>
          <CheckboxField label={t("confirm")} name="confirm_change" required />
        </>
      )}
      <div>
        <SubmitButton>{t("save")}</SubmitButton>
      </div>
    </form>
  );
}
