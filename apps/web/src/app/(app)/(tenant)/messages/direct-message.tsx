"use client";

import { MessageCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

type Props = { action: (state: FormState, formData: FormData) => Promise<FormState> };

/** A short message to one person, sent through MyBiz (simulated). */
export function DirectMessageForm({ action }: Props) {
  const t = useTranslations("messaging");
  const [state, formAction] = useActionState(action, {});
  return (
    <form action={formAction} className="flex flex-col gap-3">
      <FormFeedback state={state.error ? state : {}} />
      {state.saved && <p role="status" className="text-sm text-success">{t("sentOne")}</p>}
      <TextAreaField label={t("text")} name="body" required maxLength={1000} rows={2} />
      <input type="hidden" name="channel" value="whatsapp" />
      <div>
        <SubmitButton>
          <MessageCircle aria-hidden="true" className="size-4" />
          {t("sendViaMyBiz")}
        </SubmitButton>
      </div>
    </form>
  );
}
