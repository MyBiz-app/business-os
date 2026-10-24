"use client";

import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { Field } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { isolate } from "@/lib/bidi";
import { OTP_LENGTH, type OtpChannel } from "@/lib/otp";

import { type CodeState, sendLoginCode, verifyLoginCode } from "../../actions";

/** Sign in with a one-time code: pick where to get it (email, and SMS / WhatsApp when the
 * project offers them), then type the six digits. */
export function CodeLoginForm({ channels, next }: { channels: OtpChannel[]; next?: string }) {
  const t = useTranslations("auth");
  const [channel, setChannel] = useState<OtpChannel>("email");
  const [sent, send] = useActionState<CodeState, FormData>(sendLoginCode, {});
  const [checked, verify] = useActionState<CodeState, FormData>(verifyLoginCode, {});

  if (sent.target) {
    return (
      <form action={verify} className="flex flex-col gap-4">
        {next && <input type="hidden" name="next" value={next} />}
        <input type="hidden" name="channel" value={sent.channel} />
        <input type="hidden" name="target" value={sent.target} />
        <p className="text-sm text-muted">{t("codeLogin.codeSent", { target: isolate(sent.target) })}</p>
        <FormError inline message={checked.error && t(`errors.${checked.error}` as "errors.generic")} />
        <Field
          label={t("codeLogin.code")}
          name="code"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern={`\\d{${OTP_LENGTH}}`}
          maxLength={OTP_LENGTH}
          dir="ltr"
          required
          autoFocus
        />
        <SubmitButton>{t("codeLogin.verify")}</SubmitButton>
        <a href={next ? `/login/code?next=${encodeURIComponent(next)}` : "/login/code"} className="btn-secondary px-4 py-2.5 text-center">
          {t("codeLogin.change")}
        </a>
      </form>
    );
  }

  return (
    <form action={send} className="flex flex-col gap-4">
      <input type="hidden" name="channel" value={channel} />
      <FormError inline message={sent.error && t(`errors.${sent.error}` as "errors.generic")} />
      {channels.length > 1 && (
        <fieldset className="flex flex-col gap-1.5">
          <legend className="text-sm font-medium">{t("codeLogin.channel")}</legend>
          <div className="flex flex-wrap gap-2">
            {channels.map((option) => (
              <button
                key={option}
                type="button"
                aria-pressed={channel === option}
                onClick={() => setChannel(option)}
                className={channel === option ? "btn-primary px-4 py-2" : "btn-secondary px-4 py-2"}
              >
                {t(`codeLogin.channels.${option}` as "codeLogin.channels.email")}
              </button>
            ))}
          </div>
        </fieldset>
      )}
      {channel === "email" ? (
        <Field label={t("email")} name="email" type="email" autoComplete="email" required />
      ) : (
        <Field label={t("codeLogin.phone")} name="phone" type="tel" autoComplete="tel" required />
      )}
      <SubmitButton>{t("codeLogin.send")}</SubmitButton>
    </form>
  );
}
