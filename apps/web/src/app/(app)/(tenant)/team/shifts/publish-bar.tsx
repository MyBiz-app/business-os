"use client";

import { CheckCircle2, Send } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import { type PublishState, publishShifts } from "./actions";

/** Managers: how many shifts of the visible stretch are still drafts, and a button to send them
 * to the team now. Until a shift is published only managers see it. */
export function PublishBar({ drafts, start, days, branches, summary }: { drafts: number; start: string; days: number; branches: string[]; summary: string }) {
  const t = useTranslations("shifts.publish");
  const [state, setState] = useState<PublishState>({});
  const [pending, startTransition] = useTransition();

  return (
    <div className={`flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border px-4 py-2.5 text-sm ${drafts > 0 ? "border-warning/40 bg-warning/10" : "border-border bg-surface"}`}>
      <p role="status" className="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1">
        {drafts > 0 ? (
          <span className="font-medium">{t("drafts", { count: drafts })}</span>
        ) : (
          <span className="flex items-center gap-1.5 text-muted">
            <CheckCircle2 aria-hidden="true" className="size-4 text-success" />
            {state.published ? t("done", { count: state.published }) : t("allPublished")}
          </span>
        )}
        <span className="text-xs text-muted">{summary}</span>
      </p>
      {state.error && (
        <span role="alert" className="text-danger">
          {t("error")}
        </span>
      )}
      {drafts > 0 && (
        <button
          type="button"
          disabled={pending}
          aria-busy={pending}
          onClick={() => startTransition(async () => setState(await publishShifts(start, days, branches)))}
          className="btn-primary gap-1.5 px-3 py-1.5"
        >
          <Send aria-hidden="true" className="size-4 rtl:-scale-x-100" />
          {t("now")}
        </button>
      )}
    </div>
  );
}
