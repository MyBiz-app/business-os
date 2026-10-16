"use client";

import type { components } from "@business-os/api-client";
import { Check, Circle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

import { updateLegalDetails } from "./actions";

type Tenant = components["schemas"]["Tenant"];
type Readiness = components["schemas"]["Readiness"];

/** The legal-readiness card: a checklist of what the business has told us, what each missing
 * piece would unlock, and the form for the address, employer file and optional licence.
 * Nothing here blocks the product; a missing piece only holds back the one action it serves. */
export function LegalReadiness({ tenant, readiness }: { tenant: Tenant; readiness: Readiness }) {
  const t = useTranslations("settings.readiness");
  const tCommon = useTranslations("common");
  const [state, action] = useActionState<FormState, FormData>(updateLegalDetails, {});
  const licenseNote =
    readiness.license_status === "expired"
      ? t("license.expired")
      : readiness.license_status === "expiring"
        ? t("license.expiring", { days: readiness.license_days_left ?? 0 })
        : null;
  const capabilities = [
    { key: "taxInvoice", on: readiness.tax_invoice, label: readiness.tax_invoice ? t("capability.taxInvoice.on") : t("capability.taxInvoice.off") },
    { key: "payroll", on: readiness.payroll, label: readiness.payroll ? t("capability.payroll.on") : t("capability.payroll.off") },
  ];

  return (
    <div className="flex flex-col gap-6">
      <ul className="flex flex-col gap-2">
        {readiness.items.map((item) => (
          <li key={item.key} className="flex items-start gap-3 text-sm">
            <span aria-hidden="true" className={`mt-0.5 ${item.done ? "text-success" : "text-muted"}`}>
              {item.done ? <Check className="size-4" /> : <Circle className="size-4" />}
            </span>
            <span className="flex flex-col gap-0.5">
              <span className="font-medium">
                {t(`items.${item.key}`)}
                {item.optional && <span className="ms-2 text-xs font-normal text-muted">{t("optional")}</span>}
              </span>
              {!item.done && item.unlocks && <span className="text-muted">{t(`unlocks.${item.unlocks}`)}</span>}
              {item.warning && (
                <span role="note" className="text-warning">
                  {t(`warnings.${item.warning}`)}
                </span>
              )}
              {item.key === "license" && licenseNote && (
                <span role="note" className="text-warning">
                  {licenseNote}
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>

      <ul className="flex flex-wrap gap-2" aria-label={t("capabilities")}>
        {capabilities.map(({ key, on, label }) => (
          <li key={key} className={`rounded-full px-3 py-1 text-xs font-medium ${on ? "bg-success/10 text-success" : "bg-muted/10 text-muted"}`}>
            {label}
          </li>
        ))}
        {readiness.receipts_only && <li className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">{t("receiptsOnly")}</li>}
      </ul>

      <form action={action} className="flex flex-col gap-4 border-t border-border pt-6">
        <FormError message={state.error && tCommon("errors.generic")} />
        <FormNotice message={state.saved ? tCommon("saved") : undefined} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("form.addressLine")} name="address_line" defaultValue={tenant.address_line ?? ""} maxLength={200} autoComplete="street-address" />
          <Field label={t("form.addressCity")} name="address_city" defaultValue={tenant.address_city ?? ""} maxLength={100} autoComplete="address-level2" />
          <Field label={t("form.employerFile")} hint={t("form.employerFileHint")} name="employer_file_number" defaultValue={tenant.employer_file_number ?? ""} maxLength={20} dir="ltr" autoComplete="off" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("form.licenseNumber")} hint={t("form.licenseHint")} name="business_license_number" defaultValue={tenant.business_license_number ?? ""} maxLength={40} dir="ltr" autoComplete="off" />
          <Field label={t("form.licenseExpires")} name="business_license_expires_on" type="date" defaultValue={tenant.business_license_expires_on ?? ""} />
        </div>
        <div>
          <SubmitButton>{tCommon("save")}</SubmitButton>
        </div>
      </form>
    </div>
  );
}
