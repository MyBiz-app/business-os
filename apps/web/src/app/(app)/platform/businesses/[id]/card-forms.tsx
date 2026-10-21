"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type ActionState, addNote, saveCard } from "./actions";

function useFeedback() {
  const t = useTranslations("platform.card");
  return (state: ActionState) => (state.error ? t(`errors.${state.error as "generic"}`) : undefined);
}

/** Tags and the MyBiz team member who looks after the business: internal, edited by the team. */
export function CardForm({
  tenantId,
  tags,
  accountOwner,
  mayAct,
}: {
  tenantId: string;
  tags: string[];
  accountOwner: string | null;
  mayAct: boolean;
}) {
  const t = useTranslations("platform.card");
  const error = useFeedback();
  const [state, action] = useActionState<ActionState, FormData>(saveCard.bind(null, tenantId), {});
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormError message={error(state)} />
      <FormNotice message={state.done ? t("saved") : undefined} />
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium">{t("tags")}</span>
        <input name="tags" defaultValue={tags.join(", ")} readOnly={!mayAct} dir="auto" className="control w-full px-3 py-2" />
        <span className="text-muted">{t("tagsHint")}</span>
      </label>
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium">{t("accountOwner")}</span>
        <input
          name="account_owner"
          type="email"
          defaultValue={accountOwner ?? ""}
          readOnly={!mayAct}
          dir="ltr"
          className="control w-full px-3 py-2"
        />
        <span className="text-muted">{t("accountOwnerHint")}</span>
      </label>
      {mayAct && (
        <div>
          <SubmitButton>{t("save")}</SubmitButton>
        </div>
      )}
    </form>
  );
}

/** Writes an internal note ("I spoke to them, they want X"). */
export function NoteForm({ tenantId }: { tenantId: string }) {
  const t = useTranslations("platform.card");
  const error = useFeedback();
  const [state, action] = useActionState<ActionState, FormData>(addNote.bind(null, tenantId), {});
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormError message={error(state)} />
      <FormNotice message={state.done ? t("noteAdded") : undefined} />
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium">{t("noteLabel")}</span>
        <textarea
          name="body"
          required
          maxLength={2000}
          rows={3}
          dir="auto"
          placeholder={t("notePlaceholder")}
          className="control w-full px-3 py-2"
        />
      </label>
      <div>
        <SubmitButton>{t("addNote")}</SubmitButton>
      </div>
    </form>
  );
}
