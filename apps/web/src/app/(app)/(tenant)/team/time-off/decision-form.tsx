"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";

import { decideRequest } from "./actions";

export function DecisionForm({ requestId }: { requestId: string }) {
  const t = useTranslations("timeOffQueue");
  const [state, action, pending] = useActionState(decideRequest.bind(null, requestId), {});
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormFeedback state={state} />
      <Field label={t("note")} name="note" maxLength={200} hint={t("noteHint")} />
      <div className="flex flex-wrap gap-2">
        <button type="submit" name="decision" value="approve" disabled={pending} className="btn-primary px-4 py-2.5">
          {t("approve")}
        </button>
        <button type="submit" name="decision" value="decline" disabled={pending} className="btn-secondary px-4 py-2.5">
          {t("decline")}
        </button>
      </div>
    </form>
  );
}
