"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { isolate } from "@/lib/bidi";

import { type ContactEmailState, resendContactEmail, saveContactEmail } from "./contact-email-actions";

type State = components["schemas"]["ContactEmails"];
type PurposeState = State["purposes"][number];

function PurposeForm({ locationId, item }: { locationId: string | null; item: PurposeState }) {
  const t = useTranslations("settings.contactEmails");
  const tCommon = useTranslations("common");
  const [state, action] = useActionState<ContactEmailState, FormData>(saveContactEmail.bind(null, locationId, item.purpose), {});
  const [resent, resend] = useActionState<ContactEmailState>(resendContactEmail.bind(null, locationId, item.purpose), {});
  const latest = resent.saved ? resent : state;
  const source = item.effective_source === "branch" ? null : item.effective_source === "business" ? t("fromBusiness") : t("fromOwner");
  const pending = item.email !== null && !item.verified;
  return (
    <div className="flex flex-col gap-2 border-t border-border pt-4 first:border-t-0 first:pt-0">
      <form action={action} className="flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1">
          <Field
            key={item.email ?? ""}
            label={t(`purposes.${item.purpose}`)}
            name="email"
            type="email"
            defaultValue={item.email ?? ""}
            placeholder={item.effective_email ?? t("emailLabel")}
            maxLength={254}
          />
        </div>
        <SubmitButton variant="secondary" className="px-3 py-2">
          {t("save")}
        </SubmitButton>
      </form>
      <FormError message={state.error && (state.error === "invalid" ? t("invalid") : tCommon(`errors.${state.error}`))} />
      {item.email !== null && item.verified && <p className="text-sm text-success">{t("verified")}</p>}
      {pending && (
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
          <span>{t("pending", { email: isolate(item.email ?? "") })}</span>
          <form action={resend}>
            <SubmitButton variant="secondary" className="px-3 py-1.5">
              {t("resend")}
            </SubmitButton>
          </form>
        </div>
      )}
      {latest.saved && latest.sent !== undefined && latest.sent !== null && (
        <p role="status" className="text-sm text-muted">
          {latest.sent ? t("sent") : t("notSent")}
        </p>
      )}
      {item.effective_email && (
        <p className="text-sm text-muted">
          {t("usedNow", { email: isolate(item.effective_email) })}
          {source && ` · ${source}`}
        </p>
      )}
    </div>
  );
}

/** The addresses of the business, or (with a branch) of that branch; unset ones fall back. */
export function ContactEmails({ data, locationId }: { data: State; locationId: string | null }) {
  const t = useTranslations("settings.contactEmails");
  return (
    <section aria-labelledby={`contact-emails-${locationId ?? "business"}`} className="flex flex-col gap-4 card p-6">
      <div className="flex flex-col gap-1">
        <h2 id={`contact-emails-${locationId ?? "business"}`} className="text-lg font-semibold">
          {locationId ? t("branchTitle") : t("title")}
        </h2>
        <p className="text-sm text-muted">{locationId ? t("branchHint") : t("hint")}</p>
      </div>
      {data.purposes.map((item) => (
        <PurposeForm key={item.purpose} locationId={locationId} item={item} />
      ))}
    </section>
  );
}
