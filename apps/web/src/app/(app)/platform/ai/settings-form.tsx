"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type AiState, saveAiSettings } from "./actions";

type Choice = { id: string; tier: "fast" | "standard" | "strong"; enabled: boolean };
type Props = {
  killAll: boolean;
  chosen: { fast: string | null; standard: string | null; strong: string | null };
  defaults: Record<string, string>;
  choices: Choice[];
  canChange: boolean;
};

const TIERS = ["fast", "standard", "strong"] as const;

/** Which model serves each tier, and the emergency stop that halts AI for every business. */
export function AiSettingsForm({ killAll, chosen, defaults, choices, canChange }: Props) {
  const t = useTranslations("platform.ai");
  const [state, action] = useActionState<AiState, FormData>(saveAiSettings, {});
  return (
    <form action={action} className="flex flex-col gap-5">
      <FormError message={state.error ? t(`errors.${state.error}` as "errors.generic") : undefined} />
      <FormNotice message={state.saved ? t("saved") : undefined} />
      <fieldset disabled={!canChange} className="grid gap-4 sm:grid-cols-3">
        {TIERS.map((tier) => (
          <div key={tier} className="flex flex-col gap-1.5">
            <label htmlFor={`model-${tier}`} className="text-sm font-medium">
              {t(`tiers.${tier}`)}
            </label>
            <select id={`model-${tier}`} name={`model_${tier}`} defaultValue={chosen[tier] ?? ""} className="control w-full px-3 py-2" dir="ltr">
              <option value="">{t("defaultModel", { model: defaults[tier] })}</option>
              {choices
                .filter((choice) => choice.tier === tier && choice.enabled)
                .map((choice) => (
                  <option key={choice.id} value={choice.id}>
                    {choice.id}
                  </option>
                ))}
            </select>
            <span className="text-xs text-muted">{t(`tierHints.${tier}`)}</span>
          </div>
        ))}
      </fieldset>
      <fieldset disabled={!canChange} className="flex items-start gap-3 rounded-xl border border-danger/40 bg-danger/5 p-4">
        <input id="kill-all" type="checkbox" name="kill_all" defaultChecked={killAll} className="mt-1 size-4 accent-[var(--danger)]" />
        <label htmlFor="kill-all" className="flex flex-col gap-0.5">
          <span className="font-semibold">{t("killAll")}</span>
          <span className="text-sm text-muted">{t("killAllHint")}</span>
        </label>
      </fieldset>
      {canChange ? (
        <div>
          <SubmitButton>{t("save")}</SubmitButton>
        </div>
      ) : (
        <p className="text-sm text-muted">{t("readOnly")}</p>
      )}
    </form>
  );
}
