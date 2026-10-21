"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";

import { decideSwap } from "./actions";
import { Button } from "@/components/ui/button";

export function DecisionForm({ swapId }: { swapId: string }) {
  const t = useTranslations("shiftSwapQueue");
  const [state, action, pending] = useActionState(decideSwap.bind(null, swapId), {});
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
