"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState } from "react";

import { copyWeek, type CopyWeekState } from "./actions";

/** Copies this week's one-off classes to the next week (weekly series repeat on their own). */
export function CopyWeek({ weekStart, nextWeek }: { weekStart: string; nextWeek: string }) {
  const t = useTranslations("schedule");
  const [state, action, pending] = useActionState<CopyWeekState, FormData>(copyWeek.bind(null, weekStart), {});

  return (
    <form action={action} className="flex flex-col items-end gap-1">
      <button
        type="submit"
        disabled={pending}
        aria-busy={pending}
        title={t("copyWeekHint")}
        className="btn-secondary px-3 py-2 text-sm font-medium"
      >
        {t("copyWeek")}
      </button>
      {state.copied && (
        <p role="status" className="text-sm">
          {t("copyWeekDone", { created: state.copied.created, skipped: state.copied.skipped })}{" "}
          <Link href={`/schedule?week=${nextWeek}`} className="text-primary underline-offset-4 hover:underline">
            {t("nextWeek")}
          </Link>
        </p>
      )}
      {state.error && (
        <p role="alert" className="text-sm text-danger">
          {t("copyWeekError")}
        </p>
      )}
    </form>
  );
}
