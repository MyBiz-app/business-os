"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type AiState, saveWebSearch } from "./actions";

type Props = { enabled: boolean; monthlyLimit: number; used: number; canChange: boolean };

/** Web search for the console agents: off by default, with a limit on searches per month. */
export function WebSearchForm({ enabled, monthlyLimit, used, canChange }: Props) {
  const t = useTranslations("platform.ai");
  const [state, action] = useActionState<AiState, FormData>(saveWebSearch, {});
  return (
    <form action={action} className="flex flex-col gap-4">
      <FormError message={state.error ? t(`errors.${state.error}` as "errors.generic") : undefined} />
      <FormNotice message={state.saved ? t("saved") : undefined} />
      <fieldset disabled={!canChange} className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <input id="web-search-enabled" type="checkbox" name="enabled" defaultChecked={enabled} className="size-4" />
          <label htmlFor="web-search-enabled" className="font-medium">
            {t("webSearch.enabled")}
          </label>
        </div>
        <div className="flex max-w-xs flex-col gap-1.5">
          <label htmlFor="web-search-limit" className="text-sm font-medium">
            {t("webSearch.limit")}
          </label>
          <input id="web-search-limit" name="monthly_limit" type="number" min={0} max={1000} defaultValue={monthlyLimit} className="control w-full px-3 py-2" dir="ltr" />
          <span className="text-xs text-muted">{t("webSearch.used", { count: used })}</span>
        </div>
      </fieldset>
      {canChange ? (
        <div>
          <SubmitButton>{t("save")}</SubmitButton>
        </div>
      ) : (
        <p className="text-sm text-muted">{t("webSearch.forbidden")}</p>
      )}
    </form>
  );
}
