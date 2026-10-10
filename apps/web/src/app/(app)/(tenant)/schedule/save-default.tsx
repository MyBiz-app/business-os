"use client";

import { Bookmark } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { saveScheduleDefault, type DefaultViewState } from "./actions";

/** Owners: keeps the current range and branches as the way the schedule opens for the business. */
export function SaveDefault({ view, branches }: { view: "day" | "week" | "month"; branches: string[] }) {
  const t = useTranslations("schedule");
  const [state, action, pending] = useActionState<DefaultViewState, FormData>(saveScheduleDefault.bind(null, view, branches), {});

  return (
    <form action={action} className="flex items-center gap-2">
      <button type="submit" disabled={pending} aria-busy={pending} title={t("saveDefaultHint")} className="btn-ghost gap-1.5 px-3 py-1.5 text-sm">
        <Bookmark aria-hidden="true" className="size-4" />
        {t("saveDefault")}
      </button>
      {state.saved && (
        <span role="status" className="text-sm text-muted">
          {t("defaultSaved")}
        </span>
      )}
      {state.error && (
        <span role="alert" className="text-sm text-danger">
          {t("defaultError")}
        </span>
      )}
    </form>
  );
}
