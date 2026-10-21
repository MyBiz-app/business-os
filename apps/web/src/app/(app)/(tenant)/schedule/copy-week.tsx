"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState } from "react";

import { copyWeek, type CopyWeekState } from "./actions";
import { FormError, FormNotice } from "@/components/form/form-message";
import { Button } from "@/components/ui/button";

/** Copies this week's one-off classes to the next week (weekly series repeat on their own). */
export function CopyWeek({ weekStart, nextWeek }: { weekStart: string; nextWeek: string }) {
  const t = useTranslations("schedule");
  const [state, action, pending] = useActionState<CopyWeekState, FormData>(copyWeek.bind(null, weekStart), {});

  return (
    <form action={action} className="flex flex-col items-end gap-1">
      <Button
        variant="secondary"
        type="submit"
        disabled={pending}
        aria-busy={pending}
        title={t("copyWeekHint")}
      >
        {t("copyWeek")}
      </Button>
      <FormNotice message={state.copied ? t("copyWeekDone", { created: state.copied.created, skipped: state.copied.skipped }) : undefined} />
      {state.copied && (
        <Link scroll={false} href={`/schedule?week=${nextWeek}`} className="text-sm text-primary-ink underline-offset-4 hover:underline">
          {t("nextWeek")}
        </Link>
      )}
      <FormError message={state.error ? t("copyWeekError") : undefined} />
    </form>
  );
}
