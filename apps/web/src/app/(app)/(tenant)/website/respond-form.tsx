"use client";

import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { respondToSite } from "./actions";

/** The business looks at the finished site and approves it or asks for changes. */
export function RespondForm() {
  const t = useTranslations("website");
  const [state, action] = useActionState(respondToSite, {});
  const [asking, setAsking] = useState(false);
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormFeedback state={state} />
      {asking && <TextAreaField label={t("review.changesLabel")} name="message" required maxLength={2000} rows={3} />}
      <div className="flex flex-wrap items-center gap-3">
        {asking ? (
          <>
            <button type="submit" name="action" value="changes" className="btn-plain btn-primary px-4 py-2.5">{t("review.sendChanges")}</button>
            <button type="button" className="btn-plain btn-secondary px-4 py-2.5" onClick={() => setAsking(false)}>{t("review.cancel")}</button>
          </>
        ) : (
          <>
            <input type="hidden" name="action" value="approve" />
            <SubmitButton>{t("review.approve")}</SubmitButton>
            <button type="button" className="btn-plain btn-secondary px-4 py-2.5" onClick={() => setAsking(true)}>{t("review.askChanges")}</button>
          </>
        )}
      </div>
    </form>
  );
}
