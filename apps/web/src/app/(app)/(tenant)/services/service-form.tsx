"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState } from "react";

import { CheckboxField, Field, TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";
import { toMajorUnits } from "@/lib/money";

type Service = components["schemas"]["Service"];

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

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      {/* Remount after a save so fields show the stored values (see ClientForm). */}
      <fieldset key={service?.updated_at ?? "new"} disabled={readOnly} className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Field label={t("services.name")} name="name" required maxLength={120} defaultValue={service?.name} />
        </div>
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
        <Field
          label={`${t("services.price")} (${currency})`}
          name="price"
          inputMode="decimal"
          dir="ltr"
          pattern="\d+([.,]\d{1,2})?"
          defaultValue={service ? toMajorUnits(service.price_amount) : ""}
        />
        <Field label={t("services.color")} name="color" type="color" defaultValue={service?.color ?? "#4f46e5"} />
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
