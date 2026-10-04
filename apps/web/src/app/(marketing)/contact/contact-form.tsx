"use client";

import { CheckCircle2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field, SelectField, TextAreaField } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type ContactState, sendContact } from "./actions";

const VERTICALS = ["fitness", "beauty", "clinic", "garage", "other"] as const;

export function ContactForm() {
  const t = useTranslations("marketing.contact");
  const [state, action] = useActionState<ContactState, FormData>(sendContact, {});

  if (state.sent) {
    return (
      <div role="status" className="flex flex-col items-center gap-3 py-10 text-center">
        <CheckCircle2 aria-hidden="true" className="size-14 text-success" />
        <p className="text-lg font-semibold">{t("sent")}</p>
      </div>
    );
  }

  return (
    <form action={action} className="flex flex-col gap-4">
      <FormError message={state.error && t(`errors.${state.error}`)} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("name")} name="name" required minLength={2} maxLength={120} autoComplete="name" />
        <Field label={t("email")} name="email" type="email" required autoComplete="email" dir="ltr" />
        <Field label={t("phone")} name="phone" type="tel" maxLength={40} autoComplete="tel" dir="ltr" />
        <Field label={t("business")} name="business" maxLength={160} autoComplete="organization" />
      </div>
      <SelectField
        label={t("vertical")}
        name="vertical"
        defaultValue="fitness"
        options={VERTICALS.map((value) => ({ value, label: t(`verticals.${value}`) }))}
      />
      <TextAreaField label={t("message")} name="message" maxLength={4000} />
      {/* Hidden from people; bots fill it in (see the API). */}
      <div aria-hidden="true" className="absolute -start-[9999px] size-px overflow-hidden">
        <label>
          {t("website")}
          <input name="website" tabIndex={-1} autoComplete="off" />
        </label>
      </div>
      <div>
        <SubmitButton>{t("send")}</SubmitButton>
      </div>
    </form>
  );
}
