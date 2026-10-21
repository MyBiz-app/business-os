"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useActionState } from "react";

import { publishWeek, type PublishWeekState } from "./actions";
import { FormError, FormNotice } from "@/components/form/form-message";
import { Button } from "@/components/ui/button";

/** Opens the next week of classes for clients now (the weekly release would do it later). */
export function PublishWeek() {
  const t = useTranslations("schedule");
  const format = useFormatter();
  const [state, action, pending] = useActionState<PublishWeekState, FormData>(publishWeek, {});

  return (
    <form action={action} className="flex flex-col items-end gap-1">
      <Button variant="secondary" type="submit" disabled={pending} aria-busy={pending} title={t("publishWeekHint")}>
        {t("publishWeek")}
      </Button>
      <FormNotice
        message={
          state.published
            ? t("publishWeekDone", { date: format.dateTime(new Date(`${state.published}T12:00:00Z`), { dateStyle: "medium", timeZone: "UTC" }) })
            : state.already
              ? t("publishWeekAlready")
              : undefined
        }
      />
      <FormError message={state.error ? t("publishWeekError") : undefined} />
    </form>
  );
}
