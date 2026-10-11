"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState, useState } from "react";

import { CheckboxField, Field, SelectField, TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";
import { toMajorUnits } from "@/lib/money";

type Service = components["schemas"]["Service"];

const LENGTHS = [30, 45, 60, 90, 120, 150, 180, 240];
const STEPS = [15, 30, 60];
const TRAVEL = [0, 15, 30, 45, 60, 90];

type Props = {
  action: (state: FormState, formData: FormData) => Promise<FormState>;
  service?: Service;
  currency: string;
  submitLabel: string;
  readOnly?: boolean;
};

export function ServiceForm({ action, service, currency, submitLabel, readOnly = false }: Props) {
  const t = useTranslations();
  const [state, formAction] = useActionState(action, {});
  const [mode, setMode] = useState<Service["booking_mode"]>(service?.booking_mode ?? "class");
  const [onSite, setOnSite] = useState(service?.on_site ?? false);

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      {/* Remount after a save so fields show the stored values (see ClientForm). */}
      <fieldset key={service?.updated_at ?? "new"} disabled={readOnly} className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Field label={t("services.name")} name="name" required maxLength={120} defaultValue={service?.name} />
        </div>
        {mode === "resource" ? (
          // A reservation's length is chosen by the client; the service keeps a nominal one.
          <input type="hidden" name="duration_minutes" value={service?.duration_minutes ?? 60} />
        ) : (
          <Field
            label={t("services.duration")}
            name="duration_minutes"
            type="number"
            min={5}
            max={1440}
            step={5}
            required
            defaultValue={service?.duration_minutes ?? 60}
          />
        )}
        <SelectField
          label={t("services.bookingMode")}
          name="booking_mode"
          value={mode}
          onChange={(event) => setMode(event.target.value as Service["booking_mode"])}
          options={(["class", "appointment", "resource"] as const).map((value) => ({ value, label: t(`services.modes.${value}`) }))}
        />
        {mode === "resource" && (
          <>
            <p className="text-sm text-muted sm:col-span-2">{t("resources.serviceHint")}</p>
            <SelectField
              label={t("resources.minLength")}
              name="min_minutes"
              defaultValue={String(service?.min_minutes ?? 60)}
              options={LENGTHS.map((value) => ({ value: String(value), label: t("services.minutes", { count: value }) }))}
            />
            <SelectField
              label={t("resources.maxLength")}
              name="max_minutes"
              defaultValue={String(service?.max_minutes ?? 120)}
              options={LENGTHS.map((value) => ({ value: String(value), label: t("services.minutes", { count: value }) }))}
            />
            <SelectField
              label={t("resources.step")}
              name="step_minutes"
              defaultValue={String(service?.step_minutes ?? 30)}
              options={STEPS.map((value) => ({ value: String(value), label: t("services.minutes", { count: value }) }))}
            />
            <Field
              label={`${t("resources.pricePerHour")} (${currency})`}
              name="price_per_hour"
              inputMode="decimal"
              dir="ltr"
              required
              pattern="\d+([.,]\d{1,2})?"
              defaultValue={service?.price_per_hour != null ? toMajorUnits(service.price_per_hour, currency) : ""}
            />
          </>
        )}
        {mode === "appointment" && (
          <>
            <div className="sm:col-span-2">
              <CheckboxField
                label={t("jobs.onSite")}
                name="on_site"
                checked={onSite}
                onChange={(event) => setOnSite(event.target.checked)}
              />
              <p className="mt-1 text-sm text-muted">{t("jobs.onSiteHint")}</p>
            </div>
            {onSite && (
              <SelectField
                label={t("jobs.travel")}
                name="travel_minutes"
                defaultValue={String(service?.travel_minutes ?? 30)}
                options={TRAVEL.map((value) => ({ value: String(value), label: t("services.minutes", { count: value }) }))}
              />
            )}
          </>
        )}
        {mode === "class" ? (
          <Field
            label={t("services.capacity")}
            hint={t("services.capacityHint")}
            name="capacity"
            type="number"
            min={1}
            max={1000}
            required
            defaultValue={service?.capacity ?? 1}
          />
        ) : (
          <input type="hidden" name="capacity" value={1} />
        )}
        {mode === "resource" ? (
          <input type="hidden" name="price" value={service ? toMajorUnits(service.price_amount, currency) : "0"} />
        ) : (
          <Field
            label={`${t("services.price")} (${currency})`}
            name="price"
            inputMode="decimal"
            dir="ltr"
            pattern="\d+([.,]\d{1,2})?"
            defaultValue={service ? toMajorUnits(service.price_amount, currency) : ""}
          />
        )}
        <Field label={t("services.color")} name="color" type="color" defaultValue={service?.color ?? "#4f46e5"} className="control h-11 w-20 cursor-pointer p-1" />
        <div className="sm:col-span-2">
          <TextAreaField label={t("services.description")} name="description" maxLength={2000} defaultValue={service?.description ?? ""} />
        </div>
        <CheckboxField label={t("services.active")} name="active" defaultChecked={service?.active ?? true} />
      </fieldset>
      {!readOnly && (
        <div className="flex items-center gap-4">
          <SubmitButton>{submitLabel}</SubmitButton>
          <Link href="/services" className="text-sm text-muted underline-offset-4 hover:underline">
            {t("common.cancel")}
          </Link>
        </div>
      )}
    </form>
  );
}
