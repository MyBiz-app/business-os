"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState } from "react";

import { Field, SelectField, TextAreaField } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import type { ClientFormState } from "./actions";

type Client = components["schemas"]["Client"];

type Props = {
  action: (state: ClientFormState, formData: FormData) => Promise<ClientFormState>;
  client?: Client;
  submitLabel: string;
  readOnly?: boolean;
};

const STATUSES = ["active", "lead", "inactive"] as const;

export function ClientForm({ action, client, submitLabel, readOnly = false }: Props) {
  const t = useTranslations("clients");
  const tAuth = useTranslations("auth");
  const [state, formAction] = useActionState(action, {});

  const errorMessage =
    state.error === "email_taken" || state.error === "invalid"
      ? t(`errors.${state.error}`)
      : state.error && tAuth("errors.generic");

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <FormError message={errorMessage} />
      <FormNotice message={state.saved ? t("saved") : undefined} />
      {/* Keyed by the saved version: after a save the fields remount with the stored values
          instead of React's form reset restoring the values the page first loaded with. */}
      <ClientFields key={client?.updated_at ?? "new"} client={client} readOnly={readOnly} />
      {!readOnly && (
        <div className="flex items-center gap-4">
          <SubmitButton>{submitLabel}</SubmitButton>
          <Link href="/clients" className="text-sm text-muted underline-offset-4 hover:underline">
            {t("cancel")}
          </Link>
        </div>
      )}
    </form>
  );
}

function ClientFields({ client, readOnly }: { client?: Client; readOnly: boolean }) {
  const t = useTranslations("clients");
  return (
    <fieldset disabled={readOnly} className="grid gap-4 sm:grid-cols-2">
        <Field label={t("firstName")} name="first_name" required maxLength={100} defaultValue={client?.first_name} />
        <Field label={t("lastName")} name="last_name" maxLength={100} defaultValue={client?.last_name ?? ""} />
        <Field label={t("phone")} name="phone" type="tel" dir="ltr" maxLength={30} defaultValue={client?.phone ?? ""} />
        <Field label={t("email")} name="email" type="email" dir="ltr" defaultValue={client?.email ?? ""} />
        <Field label={t("dateOfBirth")} name="date_of_birth" type="date" defaultValue={client?.date_of_birth ?? ""} />
        <SelectField
          label={t("status")}
          name="status"
          defaultValue={client?.status ?? "active"}
          options={STATUSES.map((value) => ({ value, label: t(`statuses.${value}`) }))}
        />
        <div className="sm:col-span-2">
          <TextAreaField label={t("notes")} name="notes" maxLength={5000} defaultValue={client?.notes ?? ""} />
        </div>
    </fieldset>
  );
}
