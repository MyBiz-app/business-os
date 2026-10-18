"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { CheckboxField, SelectField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

import { updateServiceWaitlist, updateWaitlist } from "./actions";

type Tenant = components["schemas"]["Tenant"];

const MODES = ["off", "auto", "first_come", "manual"] as const;
const AUTO_HOURS = [0, 1, 2, 3, 6, 12, 24, 48];

/** The business's switch and the mode for each kind of booking. */
export function WaitlistForm({ tenant }: { tenant: Tenant }) {
  const t = useTranslations("settings.waitlist");
  const [state, action] = useActionState<FormState, FormData>(updateWaitlist, {});
  const options = MODES.map((value) => ({ value, label: t(`modes.${value}`) }));
  return (
    <form action={action} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <div key={`${tenant.waitlist_enabled}-${tenant.waitlist_class_mode}-${tenant.waitlist_appointment_mode}-${tenant.waitlist_resource_mode}-${tenant.waitlist_auto_hours}`} className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <CheckboxField label={t("enabled")} name="waitlist_enabled" defaultChecked={tenant.waitlist_enabled} />
          <p className="mt-1.5 text-xs text-muted">{t("enabledHint")}</p>
        </div>
        <SelectField label={t("classes")} name="waitlist_class_mode" defaultValue={tenant.waitlist_class_mode} options={options} />
        <SelectField label={t("appointments")} name="waitlist_appointment_mode" defaultValue={tenant.waitlist_appointment_mode} options={options} />
        <SelectField label={t("resources")} name="waitlist_resource_mode" defaultValue={tenant.waitlist_resource_mode} options={options} />
        <SelectField
          label={t("autoHours")}
          name="waitlist_auto_hours"
          defaultValue={String(tenant.waitlist_auto_hours)}
          options={[...new Set([...AUTO_HOURS, tenant.waitlist_auto_hours])]
            .sort((a, b) => a - b)
            .map((hours) => ({ value: String(hours), label: t("hoursBefore", { hours }) }))}
        />
        <p className="text-xs text-muted sm:col-span-2">{t("autoHoursHint")}</p>
        <ul className="flex flex-col gap-1 text-xs text-muted sm:col-span-2">
          {MODES.map((mode) => (
            <li key={mode}>
              <span className="font-semibold text-foreground">{t(`modes.${mode}`)}</span>: {t(`modeHints.${mode}`)}
            </li>
          ))}
        </ul>
      </div>
      <div>
        <SubmitButton>{t("save")}</SubmitButton>
      </div>
    </form>
  );
}

/** One service that may work differently from the business setting. */
export function ServiceWaitlistRow({ id, name, mode }: { id: string; name: string; mode: string }) {
  const t = useTranslations("settings.waitlist");
  const [state, action] = useActionState<FormState, FormData>(updateServiceWaitlist.bind(null, id), {});
  return (
    <li className="py-3">
      <form action={action} className="flex flex-wrap items-end gap-3">
        <FormFeedback state={state} />
        <div className="min-w-0 flex-1 basis-48">
          <SelectField
            label={name}
            name="waitlist_mode"
            defaultValue={mode}
            options={[{ value: "", label: t("followBusiness") }, ...MODES.map((value) => ({ value, label: t(`modes.${value}`) }))]}
          />
        </div>
        <SubmitButton variant="secondary" className="px-3 py-2 text-sm">
          {t("save")}
        </SubmitButton>
      </form>
    </li>
  );
}
