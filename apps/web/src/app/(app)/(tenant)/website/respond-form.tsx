"use client";

import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { respondToSite } from "./actions";
import { Button } from "@/components/ui/button";

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
            <Button type="submit" name="action" value="changes" variant="primary">{t("review.sendChanges")}</Button>
            <Button variant="secondary" onClick={() => setAsking(false)}>{t("review.cancel")}</Button>
          </>
        ) : (
          <>
            <input type="hidden" name="action" value="approve" />
            <SubmitButton>{t("review.approve")}</SubmitButton>
            <Button variant="secondary" onClick={() => setAsking(true)}>{t("review.askChanges")}</Button>
          </>
        )}
      </div>
    </form>
  );
}
