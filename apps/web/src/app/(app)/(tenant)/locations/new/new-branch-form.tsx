"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState } from "react";

import { CheckboxField, Field, SelectField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

type Props = {
  action: (state: FormState, formData: FormData) => Promise<FormState>;
  chargeable: boolean;
  branches: { id: string; name: string }[];
  people: { id: string; name: string }[];
};

export function NewBranchForm({ action, chargeable, branches, people }: Props) {
  const t = useTranslations();
  const [state, formAction] = useActionState(action, {});

  return (
    <form action={formAction} className="flex flex-col gap-6">
      <FormFeedback state={state} />
      <fieldset className="grid gap-4 sm:grid-cols-2">
        <legend className="sr-only">{t("locations.addBranch.details")}</legend>
        <Field label={t("locations.name")} name="name" required maxLength={120} />
        <Field label={t("locations.address")} name="address" maxLength={300} />
        <SelectField
          label={t("locations.addBranch.copyHours")}
          name="copy_hours_from"
          defaultValue={branches[0]?.id ?? ""}
          options={[
            { value: "", label: t("locations.addBranch.setHoursLater") },
            ...branches.map((b) => ({ value: b.id, label: b.name })),
          ]}
        />
      </fieldset>
      {people.length > 0 && (
        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium">{t("locations.addBranch.staff")}</legend>
          <p className="text-xs text-muted">{t("locations.addBranch.staffHint")}</p>
          {people.map((person) => (
            <CheckboxField key={person.id} label={person.name} name="staff_user_ids" value={person.id} />
          ))}
        </fieldset>
      )}
      {chargeable && <CheckboxField label={t("locations.addBranch.accept")} name="accept_extra_charge" required />}
      <div className="flex items-center gap-4">
        <SubmitButton>{t("locations.addBranch.submit")}</SubmitButton>
        <Link href="/locations" className="text-sm text-muted underline-offset-4 hover:underline">
          {t("common.cancel")}
        </Link>
      </div>
    </form>
  );
}
