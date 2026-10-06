"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { addAddress, saveAddress } from "./addresses-actions";

type Address = components["schemas"]["Address"];

/** A client's address for on-site jobs: street, city, floor/apartment and how to get in. */
export function AddressForm({ clientId, address }: { clientId: string; address?: Address }) {
  const t = useTranslations("jobs.address");
  const [state, action] = useActionState(
    address ? saveAddress.bind(null, clientId, address.id) : addAddress.bind(null, clientId),
    {},
  );
  return (
    <form action={action} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("street")} name="street" required maxLength={200} dir="auto" autoComplete="street-address" defaultValue={address?.street ?? ""} />
        <Field label={t("city")} name="city" required maxLength={80} dir="auto" autoComplete="address-level2" defaultValue={address?.city ?? ""} />
        <Field label={t("details")} name="details" maxLength={200} dir="auto" defaultValue={address?.details ?? ""} />
        <Field label={t("label")} hint={t("labelHint")} name="label" maxLength={40} dir="auto" defaultValue={address?.label ?? ""} />
        <div className="sm:col-span-2">
          <Field label={t("notes")} hint={t("notesHint")} name="notes" maxLength={500} dir="auto" defaultValue={address?.notes ?? ""} />
        </div>
      </div>
      <div>
        <SubmitButton>{address ? t("save") : t("add")}</SubmitButton>
      </div>
    </form>
  );
}
