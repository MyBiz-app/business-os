"use client";

import { LifeBuoy } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type WriteState, writeToMyBiz } from "./support-actions";

/** The business writes to the MyBiz team; it lands in the console's inbox. */
export function WriteToMyBiz() {
  const t = useTranslations("support");
  const [state, action] = useActionState<WriteState, FormData>(writeToMyBiz, {});

  return (
    <section aria-labelledby="write-heading" className="flex flex-col gap-4 card p-6">
      <div className="flex flex-col gap-1">
        <h2 id="write-heading" className="flex items-center gap-2 text-lg font-semibold">
          <LifeBuoy aria-hidden="true" className="size-5 text-primary" />
          {t("writeTitle")}
        </h2>
        <p className="text-sm text-muted">{t("writeIntro")}</p>
      </div>
      <form key={state.sent ? "sent" : "draft"} action={action} className="flex flex-col gap-3">
        <FormError message={state.error ? t(`writeErrors.${state.error}`) : undefined} />
        <FormNotice message={state.sent ? t("writeSent") : undefined} />
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium">{t("writeLabel")}</span>
          <textarea name="message" rows={4} required minLength={5} maxLength={4000} dir="auto" className="control w-full px-3 py-2" />
        </label>
        <div>
          <SubmitButton>{t("writeSend")}</SubmitButton>
        </div>
      </form>
    </section>
  );
}
