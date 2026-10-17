"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { Pill } from "@/components/pill";
import type { FormState } from "@/lib/form-state";

import { setMarketingConsent } from "./consent-actions";

/** Whether the client agreed to marketing messages; staff can record or withdraw it. Service
 * messages (reminders, receipts) are sent either way. */
export function ConsentSection({ clientId, consent, canWrite }: { clientId: string; consent: boolean; canWrite: boolean }) {
  const t = useTranslations("clients.consent");
  const [state, action] = useActionState<FormState, FormData>(setMarketingConsent.bind(null, clientId, !consent), {});

  return (
    <section aria-labelledby="consent-heading" className="flex flex-col gap-3 card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="consent-heading" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <Pill tone={consent ? "success" : "muted"}>
          {consent ? t("on") : t("off")}
        </Pill>
      </div>
      <p className="text-sm text-muted">{t("hint")}</p>
      {canWrite && (
        <form action={action} className="flex flex-col gap-2">
          <FormError message={state.error && t("error")} />
          <div>
            <SubmitButton variant="secondary" className="px-4 py-2.5">
              {consent ? t("toggleOff") : t("toggleOn")}
            </SubmitButton>
          </div>
        </form>
      )}
    </section>
  );
}
