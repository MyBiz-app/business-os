"use client";

import { useActionState } from "react";
import { useTranslations } from "next-intl";

import type { components } from "@business-os/api-client";
import { Field, CheckboxField } from "@/components/form/field";
import { SubmitButton } from "@/components/form/submit-button";

import { saveDunning, type DunningState } from "./actions";

type Settings = components["schemas"]["DunningSettings"];

/** The collection steps for unpaid invoices: reminder days, read-only and suspension. */
export function DunningForm({ settings }: { settings: Settings }) {
  const t = useTranslations("platform.dunning");
  const [state, action] = useActionState<DunningState, FormData>(saveDunning, {});
  return (
    <form action={action} className="card flex flex-col gap-4 p-6">
      <h2 className="text-lg font-semibold">{t("title")}</h2>
      <p className="text-sm text-muted">{t("hint")}</p>
      <CheckboxField label={t("enabled")} name="enabled" defaultChecked={settings.enabled} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label={t("reminderDays")} name="reminder_days" defaultValue={settings.reminder_days.join(", ")} inputMode="numeric" />
        <Field label={t("readOnlyAfter")} name="read_only_after_days" type="number" min={1} max={120} defaultValue={settings.read_only_after_days} />
        <Field label={t("suspendAfter")} name="suspend_after_days" type="number" min={2} max={180} defaultValue={settings.suspend_after_days} />
      </div>
      {state.error === "invalid" && <p role="alert" className="text-sm text-danger">{t("invalid")}</p>}
      {state.saved && <p role="status" className="text-sm text-success">{t("saved")}</p>}
      <div>
        <SubmitButton>{t("save")}</SubmitButton>
      </div>
    </form>
  );
}
