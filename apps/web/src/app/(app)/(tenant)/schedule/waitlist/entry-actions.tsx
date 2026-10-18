"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { admitEntry, type EntryState, notifyEntry, removeEntry } from "./actions";

/** What the team can do with one waiting client: let them in (when a spot is free), tell them, remove them. */
export function EntryActions({ source, id, canAdmit, canNotify, name }: { source: "request" | "booking"; id: string; canAdmit: boolean; canNotify: boolean; name: string }) {
  const t = useTranslations("waitlist");
  const [admitted, admit] = useActionState<EntryState, FormData>(admitEntry.bind(null, source, id), {});
  const [removed, remove] = useActionState<EntryState, FormData>(removeEntry.bind(null, source, id), {});
  const [notified, notify] = useActionState<EntryState, FormData>(notifyEntry.bind(null, id), {});
  const message = (state: EntryState) => (state.error ? t(`errors.${state.error}`) : undefined);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {canAdmit && (
        <form action={admit}>
          <FormError message={message(admitted)} toastOnly />
          <FormNotice message={admitted.done ? t("admitted", { name }) : undefined} />
          <SubmitButton className="px-3 py-1.5 text-sm">{t("admit")}</SubmitButton>
        </form>
      )}
      {canNotify && (
        <form action={notify}>
          <FormError message={message(notified)} toastOnly />
          <FormNotice message={notified.done ? t("notified", { name }) : undefined} />
          <SubmitButton variant="secondary" className="px-3 py-1.5 text-sm">
            {t("notify")}
          </SubmitButton>
        </form>
      )}
      <form action={remove}>
        <FormError message={message(removed)} toastOnly />
        <FormNotice message={removed.done ? t("removed", { name }) : undefined} />
        <SubmitButton variant="secondary" className="px-3 py-1.5 text-sm">
          <span className="sr-only">{name}: </span>
          {t("remove")}
        </SubmitButton>
      </form>
    </div>
  );
}
