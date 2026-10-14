"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { isolate } from "@/lib/bidi";
import { OTP_LENGTH } from "@/lib/otp";

import { type PhoneState, sendPhoneCode, verifyPhoneCode } from "./phone-actions";

/** Verify a mobile number so the person can sign in with a code by SMS or WhatsApp. */
export function PhoneLogin({ verifiedPhone }: { verifiedPhone: string | null }) {
  const t = useTranslations("account.phoneLogin");
  const te = useTranslations("auth.errors");
  const [sent, send] = useActionState<PhoneState, FormData>(sendPhoneCode, {});
  const [checked, verify] = useActionState<PhoneState, FormData>(verifyPhoneCode, {});

  return (
    <div className="flex flex-col gap-4">
      {verifiedPhone && <p className="text-sm">{t("verified", { phone: isolate(`+${verifiedPhone.replace(/^\+/, "")}`) })}</p>}
      <FormNotice message={checked.done ? t("done") : undefined} />
      {sent.target && !checked.done ? (
        <form action={verify} className="flex flex-col gap-4">
          <input type="hidden" name="target" value={sent.target} />
          <p className="text-sm text-muted">{t("sent", { target: isolate(sent.target) })}</p>
          <FormError message={checked.error && te(checked.error === "generic" ? "generic" : "invalid_code")} />
          <Field label={t("code")} name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={OTP_LENGTH} dir="ltr" required />
          <SubmitButton>{t("verify")}</SubmitButton>
        </form>
      ) : (
        <form action={send} className="flex flex-col gap-4">
          <FormError message={sent.error && te(sent.error === "invalid_phone" ? "invalid_phone" : "generic")} />
          <Field label={t("phone")} name="phone" type="tel" autoComplete="tel" required />
          <SubmitButton>{t("send")}</SubmitButton>
        </form>
      )}
    </div>
  );
}
