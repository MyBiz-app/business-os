"use client";

import type { components } from "@business-os/api-client";
import { Building2, Check, CircleDot, Hand, RotateCcw } from "lucide-react";
import { isVertical } from "@business-os/verticals";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState, useState, useTransition } from "react";

import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { industryTexts } from "@/lib/verticals";

import { type InboxState, saveNotes, updateRequest } from "./actions";

type Request = components["schemas"]["ContactRequest"];

const TONE = {
  new: "bg-primary/10 text-primary",
  in_progress: "bg-warning/15",
  done: "bg-success/15",
} as const;

/** One request: who wrote, what they wrote, and the buttons that move it along. */
export function RequestCard({ request, when }: { request: Request; when: string }) {
  const t = useTranslations("platform.inbox");
  const tContact = useTranslations("marketing.contact");
  const { text } = industryTexts(useTranslations());
  const tCommon = useTranslations("common");
  const [state, action] = useActionState<InboxState, FormData>(saveNotes.bind(null, request.id), {});
  const [rowState, setRowState] = useState<InboxState>({});
  const [pending, startTransition] = useTransition();
  const move = (update: Parameters<typeof updateRequest>[1]) =>
    startTransition(async () => setRowState(await updateRequest(request.id, update)));

  return (
    <li className={`card flex flex-col gap-3 p-4 ${request.status === "done" ? "opacity-70" : ""}`}>
      <FormError message={rowState.error ? tCommon("errors.generic") : undefined} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex flex-wrap items-center gap-2">
          <span className="font-semibold" dir="auto">
            {request.name}
          </span>
          {request.business && (
            <span className="text-sm text-muted" dir="auto">
              · {request.business}
            </span>
          )}
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONE[request.status]}`}>
            {t(`statuses.${request.status}`)}
          </span>
          {request.from_business && (
            <span className="flex items-center gap-1 rounded-full bg-foreground/5 px-2.5 py-0.5 text-xs">
              <Building2 aria-hidden="true" className="size-3.5" />
              {t("fromBusiness")}
            </span>
          )}
        </span>
        <span className="text-sm text-muted">{when}</span>
      </div>

      <p className="flex flex-wrap gap-3 text-sm" dir="ltr">
        <a href={`mailto:${request.email}`} className="text-primary underline-offset-4 hover:underline">
          {request.email}
        </a>
        {request.phone && <span>{request.phone}</span>}
      </p>
      {request.vertical && <p className="text-sm text-muted">{isVertical(request.vertical) ? text(request.vertical, "name") : tContact("otherVertical")}</p>}
      {request.message && (
        <p className="whitespace-pre-wrap text-sm" dir="auto">
          {request.message}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2 text-sm">
        {request.assignee ? (
          <>
            <span className="flex items-center gap-1 text-muted">
              <CircleDot aria-hidden="true" className="size-4" />
              {t("assigned", { who: request.assignee })}
            </span>
            <button type="button" disabled={pending} onClick={() => move({ assignee: "" })} className="btn-secondary px-3 py-1.5">
              {t("unassign")}
            </button>
          </>
        ) : (
          <button type="button" disabled={pending} onClick={() => move({ assignee: "me", status: "in_progress" })} className="btn-secondary px-3 py-1.5">
            <Hand aria-hidden="true" className="size-4" />
            {t("take")}
          </button>
        )}
        {request.status === "done" ? (
          <button type="button" disabled={pending} onClick={() => move({ status: "new" })} className="btn-secondary px-3 py-1.5">
            <RotateCcw aria-hidden="true" className="size-4" />
            {t("reopen")}
          </button>
        ) : (
          <button type="button" disabled={pending} onClick={() => move({ status: "done" })} className="btn-secondary px-3 py-1.5">
            <Check aria-hidden="true" className="size-4" />
            {t("markDone")}
          </button>
        )}
        {request.tenant_id && (
          <Link href={`/platform/businesses/${request.tenant_id}`} className="font-medium text-primary underline-offset-4 hover:underline">
            {t("openBusiness")}
          </Link>
        )}
      </div>

      {/* Internal notes stay folded until someone needs them (open when there are some). */}
      <details open={Boolean(request.notes) || state.saved} className="group">
        <summary className="cursor-pointer text-sm font-medium text-primary">{t("notes")}</summary>
        <form action={action} className="mt-2 flex flex-col gap-2">
          <FormNotice message={state.saved ? tCommon("saved") : undefined} />
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="sr-only">{t("notes")}</span>
            <textarea name="notes" rows={2} maxLength={4000} defaultValue={request.notes ?? ""} dir="auto" className="control w-full px-3 py-2" />
          </label>
          <div>
            <SubmitButton>{t("saveNotes")}</SubmitButton>
          </div>
        </form>
      </details>
    </li>
  );
}
