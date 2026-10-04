"use client";

import { CheckCircle2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field, TextAreaField } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type InquiryState, sendInquiry } from "./actions";

export function InquiryForm({ code }: { code: string }) {
  const t = useTranslations("inquiry");
  const [state, action] = useActionState<InquiryState, FormData>(sendInquiry.bind(null, code), {});

  if (state.sent) {
    return (
      <div role="status" className="flex flex-col items-center gap-3 py-8 text-center">
        <CheckCircle2 aria-hidden="true" className="size-14 text-success" />
        <p className="text-lg font-semibold">{t("sent")}</p>
      </div>
    );
  }

  return (
    <form action={action} className="flex flex-col gap-4">
      <FormError message={state.error && t(`errors.${state.error}`)} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("firstName")} name="first_name" required maxLength={100} autoComplete="given-name" />
        <Field label={t("lastName")} name="last_name" maxLength={100} autoComplete="family-name" />
        <Field label={t("phone")} name="phone" type="tel" maxLength={30} autoComplete="tel" dir="ltr" />
        <Field label={t("email")} name="email" type="email" autoComplete="email" dir="ltr" />
      </div>
      <p className="text-xs text-muted">{t("contactHint")}</p>
      <TextAreaField label={t("interest")} name="interest" maxLength={2000} rows={3} />
      {/* Hidden from people; bots fill it in (see the API). */}
      <div aria-hidden="true" className="absolute -start-[9999px] size-px overflow-hidden">
        <label>
          {t("website")}
          <input name="website" tabIndex={-1} autoComplete="off" />
        </label>
      </div>
      <SubmitButton>{t("send")}</SubmitButton>
      <p className="text-xs text-muted">{t("privacy")}</p>
    </form>
  );
}
