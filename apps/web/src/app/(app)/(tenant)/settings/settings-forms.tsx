"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { CheckboxField, Field, SelectField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { brandStyle } from "@/lib/brand";
import type { FormState } from "@/lib/form-state";
import { locales } from "@/i18n/config";

import { type LogoState, updateBrandColor, updateDetails, uploadLogo } from "./actions";

type Tenant = components["schemas"]["Tenant"];

const CURRENCIES = ["ILS", "USD", "EUR"] as const;
const DEFAULT_COLOR = "#4f46e5";
const CANCELLATION_WINDOWS = [0, 60, 120, 180, 360, 720, 1440, 2880];

export function DetailsForm({ tenant, timeZones }: { tenant: Tenant; timeZones: string[] }) {
  const t = useTranslations();
  const [state, action] = useActionState<FormState, FormData>(updateDetails, {});
  return (
    <form action={action} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <div key={`${tenant.name}-${tenant.locale}-${tenant.time_zone}-${tenant.currency}-${tenant.cancellation_window_minutes}-${tenant.booking_requires_plan}-${tenant.requires_health_declaration}-${tenant.online_sales}`} className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Field label={t("onboarding.name")} name="name" required maxLength={120} defaultValue={tenant.name} />
        </div>
        <SelectField
          label={t("onboarding.locale")}
          name="locale"
          defaultValue={tenant.locale}
          options={locales.map((value) => ({ value, label: t(`locales.${value}`) }))}
        />
        <SelectField
          label={t("onboarding.currency")}
          name="currency"
          defaultValue={tenant.currency}
          options={CURRENCIES.map((value) => ({ value, label: t(`onboarding.currencies.${value}`) }))}
        />
        <div className="sm:col-span-2">
          <SelectField
            label={t("onboarding.timeZone")}
            name="time_zone"
            dir="ltr"
            defaultValue={tenant.time_zone}
            options={timeZones.map((value) => ({ value, label: value.replaceAll("_", " ") }))}
          />
        </div>
        <div className="sm:col-span-2">
          <SelectField
            label={t("settings.cancellationWindow")}
            name="cancellation_window_minutes"
            defaultValue={String(tenant.cancellation_window_minutes)}
            aria-describedby="cancellation-window-hint"
            options={[
              ...new Set([...CANCELLATION_WINDOWS, tenant.cancellation_window_minutes]),
            ]
              .sort((a, b) => a - b)
              .map((minutes) => ({
                value: String(minutes),
                label:
                  minutes === 0
                    ? t("settings.cancellationNone")
                    : t("settings.cancellationHours", { hours: minutes / 60 }),
              }))}
          />
          <p id="cancellation-window-hint" className="mt-1.5 text-xs text-muted">
            {t("settings.cancellationWindowHint")}
          </p>
        </div>
        <div className="sm:col-span-2">
          <CheckboxField
            label={t("settings.requirePlan")}
            name="booking_requires_plan"
            defaultChecked={tenant.booking_requires_plan}
          />
          <p className="mt-1.5 text-xs text-muted">{t("settings.requirePlanHint")}</p>
        </div>
        <div className="sm:col-span-2">
          <CheckboxField
            label={t("settings.requireHealth")}
            name="requires_health_declaration"
            defaultChecked={tenant.requires_health_declaration}
          />
          <p className="mt-1.5 text-xs text-muted">{t("settings.requireHealthHint")}</p>
        </div>
        <div className="sm:col-span-2">
          <CheckboxField label={t("settings.onlineSales")} name="online_sales" defaultChecked={tenant.online_sales} />
          <p className="mt-1.5 text-xs text-muted">{t("settings.onlineSalesHint")}</p>
        </div>
      </div>
      <div>
        <SubmitButton>{t("common.save")}</SubmitButton>
      </div>
    </form>
  );
}

export function BrandColorForm({ color }: { color: string | null }) {
  const t = useTranslations("settings");
  const tCommon = useTranslations("common");
  const [state, action] = useActionState<FormState, FormData>(updateBrandColor, {});
  const [preview, setPreview] = useState(color ?? DEFAULT_COLOR);
  const [useDefault, setUseDefault] = useState(color === null);

  return (
    <form action={action} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <div className="flex flex-wrap items-end gap-6">
        <Field
          label={t("color")}
          name="primary_color"
          type="color"
          value={preview}
          disabled={useDefault}
          onChange={(event) => setPreview(event.target.value)}
          className="control h-11 w-20 cursor-pointer p-1"
        />
        <CheckboxField
          label={t("useDefault")}
          name="use_default"
          checked={useDefault}
          onChange={(event) => setUseDefault(event.target.checked)}
        />
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium">{t("preview")}</span>
        <div style={brandStyle(useDefault ? null : preview)} className="brand flex items-center gap-3">
          <span className="btn-primary px-4 py-2.5">{t("previewButton")}</span>
          <span className="rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">{t("color")}</span>
        </div>
      </div>
      <div>
        <SubmitButton>{tCommon("save")}</SubmitButton>
      </div>
    </form>
  );
}

export function LogoForm() {
  const t = useTranslations("settings");
  const tCommon = useTranslations("common");
  const [state, action] = useActionState<LogoState, FormData>(uploadLogo, {});
  const error =
    state.error === "logo_too_large" || state.error === "unsupported_image"
      ? t(`errors.${state.error}`)
      : state.error && tCommon("errors.generic");

  return (
    <form action={action} className="flex flex-col gap-3">
      <FormError message={error} />
      <FormNotice message={state.saved ? tCommon("saved") : undefined} />
      <Field
        label={t("logo")}
        hint={t("logoHint")}
        name="logo"
        type="file"
        accept="image/png,image/jpeg,image/webp"
        required
      />
      <div>
        <SubmitButton>{t("uploadLogo")}</SubmitButton>
      </div>
    </form>
  );
}
