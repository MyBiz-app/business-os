"use client";

import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { closeBusiness, type ClosureState } from "@/app/(app)/closed/actions";
import { Field } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

const GRACE_DAYS = 90;

/** The owner closes the business by typing its exact name (the API checks it again). */
export function CloseSection({ name }: { name: string }) {
  const t = useTranslations("closure");
  const [state, action] = useActionState<ClosureState, FormData>(closeBusiness, {});
  const [typed, setTyped] = useState("");

  return (
    <section aria-labelledby="close-heading" className="flex flex-col gap-4 card border-danger/40 p-6">
      <div className="flex flex-col gap-1">
        <h2 id="close-heading" className="text-lg font-semibold text-danger">
          {t("title")}
        </h2>
        <p className="text-sm text-muted">{t("intro", { days: GRACE_DAYS })}</p>
      </div>
      <form action={action} className="flex flex-col gap-4">
        <FormError message={state.error && t(`errors.${state.error}`)} />
        <Field
          label={t("confirmLabel", { name })}
          name="confirm_name"
          autoComplete="off"
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
        />
        <div>
          <SubmitButton variant="danger" disabled={typed.trim() !== name}>
            {t("confirmButton")}
          </SubmitButton>
        </div>
      </form>
    </section>
  );
}
