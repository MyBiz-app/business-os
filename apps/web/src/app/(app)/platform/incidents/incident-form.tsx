"use client";

import { useTranslations } from "next-intl";
import { useActionState, useState, useTransition } from "react";

import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type IncidentState, openIncident, resolveIncident } from "./actions";

const KINDS = ["incident", "maintenance", "security"] as const;

export function OpenIncidentForm() {
  const t = useTranslations("platform.incidents");
  const [state, action] = useActionState<IncidentState, FormData>(openIncident, {});
  const [key, setKey] = useState(0);
  return (
    <form
      key={key}
      action={async (data) => {
        await action(data);
        setKey((k) => k + 1);
      }}
      className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-4 shadow-sm"
    >
      <FormError message={state.error ? t(`errors.${state.error as "generic"}`) : undefined} />
      <FormNotice message={state.saved ? t("opened") : undefined} />
      <div className="flex flex-col gap-1.5">
        <label htmlFor="incident-kind" className="text-sm font-medium">
          {t("kind")}
        </label>
        <select id="incident-kind" name="kind" className="control w-full px-3 py-2">
          {KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {t(`kinds.${kind}`)}
            </option>
          ))}
        </select>
      </div>
      {(["he", "en"] as const).map((lang) => (
        <fieldset key={lang} className="flex flex-col gap-3">
          <legend className="text-sm font-medium">{t(`language.${lang}`)}</legend>
          <input name={`title_${lang}`} aria-label={t("titleField")} placeholder={t("titleField")} maxLength={150} dir={lang === "he" ? "rtl" : "ltr"} className="control w-full px-3 py-2" />
          <textarea name={`body_${lang}`} aria-label={t("bodyField")} placeholder={t("bodyField")} maxLength={600} rows={2} dir={lang === "he" ? "rtl" : "ltr"} className="control w-full px-3 py-2" />
        </fieldset>
      ))}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="incident-url" className="text-sm font-medium">
          {t("statusUrl")}
        </label>
        <input id="incident-url" name="status_url" type="url" dir="ltr" maxLength={500} placeholder="https://" className="control w-full px-3 py-2" />
      </div>
      <div>
        <SubmitButton>{t("open")}</SubmitButton>
      </div>
    </form>
  );
}

export function ResolveButton({ id }: { id: string }) {
  const t = useTranslations("platform.incidents");
  const [pending, start] = useTransition();
  const [state, setState] = useState<IncidentState>({});
  return (
    <>
      <FormError toastOnly message={state.error ? t(`errors.${state.error as "generic"}`) : undefined} />
      <button type="button" disabled={pending} onClick={() => start(async () => setState(await resolveIncident(id)))} className="btn-plain btn-secondary px-3 py-1.5 text-sm">
        {t("resolve")}
      </button>
    </>
  );
}
