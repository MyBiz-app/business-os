"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState } from "react";

import { CheckboxField, Field } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

type Location = components["schemas"]["Location"];

type Props = {
  action: (state: FormState, formData: FormData) => Promise<FormState>;
  location?: Location;
  submitLabel: string;
  readOnly?: boolean;
};

export function LocationForm({ action, location, submitLabel, readOnly = false }: Props) {
  const t = useTranslations();
  const [state, formAction] = useActionState(action, {});

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <fieldset key={location?.updated_at ?? "new"} disabled={readOnly} className="grid gap-4 sm:grid-cols-2">
        <Field label={t("locations.name")} name="name" required maxLength={120} defaultValue={location?.name} />
        <Field label={t("locations.address")} name="address" maxLength={300} defaultValue={location?.address ?? ""} />
        {location && <CheckboxField label={t("locations.active")} name="active" defaultChecked={location.active} />}
      </fieldset>
      {!readOnly && (
        <div className="flex items-center gap-4">
          <SubmitButton>{submitLabel}</SubmitButton>
          <Link href="/locations" className="text-sm text-muted underline-offset-4 hover:underline">
            {t("common.cancel")}
          </Link>
        </div>
      )}
    </form>
  );
}
