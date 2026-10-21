"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";

import { decideRequest } from "./actions";
import { Button } from "@/components/ui/button";

export function DecisionForm({ requestId }: { requestId: string }) {
  const t = useTranslations("timeOffQueue");
  const [state, action, pending] = useActionState(decideRequest.bind(null, requestId), {});
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormFeedback state={state} />
      <Field label={t("note")} name="note" maxLength={200} hint={t("noteHint")} />
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" type="submit" name="decision" value="approve" disabled={pending}>
          {t("approve")}
        </Button>
        <Button variant="secondary" type="submit" name="decision" value="decline" disabled={pending}>
          {t("decline")}
        </Button>
      </div>
    </form>
  );
}
