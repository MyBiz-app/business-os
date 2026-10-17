"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field, SelectField, type SelectOption } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";

import { addEntry, type ClockFormState, correctEntry, deleteEntry, setApproval } from "../actions";

function useMessage() {
  const t = useTranslations("timeClock");
  return (state: ClockFormState) => ({
    error: state.error ? (t.has(`errors.${state.error}` as "errors.generic") ? t(`errors.${state.error}` as "errors.generic") : t("errors.generic")) : undefined,
    saved: state.saved ? t("saved") : undefined,
  });
}

/** Correct the times of one entry (or delete it); every change needs a reason. */
export function EntryForm({ entryId, userId, clockIn, clockOut }: { entryId: string; userId: string; clockIn: string; clockOut: string }) {
  const t = useTranslations("timeClock");
  const message = useMessage();
  const [state, action, pending] = useActionState(correctEntry.bind(null, entryId, userId), {});
  const [removed, remove, removing] = useActionState(deleteEntry.bind(null, entryId, userId), {});
  const shown = message(state.error ? state : removed);
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormError message={shown.error} />
      <FormNotice message={shown.saved} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("clockIn")} name="clock_in" type="datetime-local" defaultValue={clockIn} required />
        <Field label={t("clockOut")} name="clock_out" type="datetime-local" defaultValue={clockOut} />
      </div>
      <Field label={t("reason")} name="reason" maxLength={200} hint={t("reasonHint")} required />
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={pending} className="btn-primary px-4 py-2.5">
          {t("save")}
        </button>
        <button type="submit" formAction={remove} disabled={removing} className="btn-secondary px-4 py-2.5">
          {t("delete")}
        </button>
      </div>
    </form>
  );
}

export function NewEntryForm({ userId, branches }: { userId: string; branches: SelectOption[] }) {
  const t = useTranslations("timeClock");
  const message = useMessage();
  const [state, action, pending] = useActionState(addEntry.bind(null, userId), {});
  const shown = message(state);
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormError message={shown.error} />
      <FormNotice message={shown.saved} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("clockIn")} name="clock_in" type="datetime-local" required />
        <Field label={t("clockOut")} name="clock_out" type="datetime-local" required />
      </div>
      <SelectField label={t("branch")} name="location_id" options={branches} />
      <Field label={t("reason")} name="reason" maxLength={200} hint={t("reasonHint")} required />
      <div>
        <button type="submit" disabled={pending} className="btn-primary px-4 py-2.5">
          {t("add")}
        </button>
      </div>
    </form>
  );
}

/** Approve the month (locks it) or reopen it. */
export function ApprovalForm({ userId, month, approved }: { userId: string; month: string; approved: boolean }) {
  const t = useTranslations("timeClock");
  const message = useMessage();
  const [state, action, pending] = useActionState(setApproval.bind(null, userId, month, !approved), {});
  const shown = message(state);
  return (
    <form action={action} className="flex flex-col gap-2">
      <FormError message={shown.error} />
      <div>
        <button type="submit" disabled={pending} className={approved ? "btn-secondary px-4 py-2.5" : "btn-primary px-4 py-2.5"}>
          {approved ? t("reopen") : t("approve")}
        </button>
      </div>
    </form>
  );
}
