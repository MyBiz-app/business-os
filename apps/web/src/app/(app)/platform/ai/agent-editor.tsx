"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type AiState, saveConsoleAgent } from "./actions";
import type { AgentCard } from "./agents-map";

/** What the team may change about one agent: on or off, its name, a portrait, and the instructions it always gets. */
export function AgentEditor({ agent }: { agent: AgentCard }) {
  const t = useTranslations("platform.ai");
  const [state, action] = useActionState<AiState, FormData>(saveConsoleAgent.bind(null, agent.key), {});
  return (
    <form key={agent.key} action={action} className="flex flex-col gap-4">
      <FormError message={state.error ? t(`errors.${state.error}` as "errors.generic") : undefined} />
      <FormNotice message={state.saved ? t("saved") : undefined} />
      <input type="hidden" name="x" value={agent.x ?? ""} />
      <input type="hidden" name="y" value={agent.y ?? ""} />
      {!agent.chief && (
        <label className="flex items-center gap-3 text-sm font-medium">
          <input type="checkbox" name="enabled" defaultChecked={agent.enabled} className="size-4 accent-[var(--primary)]" />
          {t("agentEnabled")}
        </label>
      )}
      {agent.chief && <input type="hidden" name="enabled" value="on" />}
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("agentNameHe")}
          <input name="name_he" defaultValue={agent.name_he ?? ""} maxLength={60} dir="rtl" className="control px-3 py-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("agentNameEn")}
          <input name="name_en" defaultValue={agent.name_en ?? ""} maxLength={60} dir="ltr" className="control px-3 py-2 font-normal" />
        </label>
      </div>
      <label className="flex flex-col gap-1.5 text-sm font-medium">
        {t("agentPortrait")}
        <input name="portrait_url" type="url" defaultValue={agent.portrait_url ?? ""} maxLength={500} pattern="https://.*" dir="ltr" placeholder="https://" className="control px-3 py-2 font-normal" />
        <span className="text-xs font-normal text-muted">{t("agentPortraitHint")}</span>
      </label>
      <label className="flex flex-col gap-1.5 text-sm font-medium">
        {t("agentInstructions")}
        <textarea name="instructions" defaultValue={agent.instructions ?? ""} maxLength={2000} rows={4} dir="auto" className="control px-3 py-2 font-normal" />
        <span className="text-xs font-normal text-muted">{t("agentInstructionsHint")}</span>
      </label>
      <div>
        <SubmitButton>{t("save")}</SubmitButton>
      </div>
    </form>
  );
}
