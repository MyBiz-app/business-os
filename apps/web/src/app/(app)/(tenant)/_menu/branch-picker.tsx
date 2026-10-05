"use client";

import { MapPin } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useTransition } from "react";

import { switchBranch } from "./actions";

type Props = { current: string | null; branches: { id: string; name: string }[] };

/** The current branch: lists, numbers and new records in the business follow it. */
export function BranchPicker({ current, branches }: Props) {
  const t = useTranslations("businessMenu");
  const id = useId();
  const [pending, start] = useTransition();
  return (
    <form
      action={(data) => start(() => switchBranch(data))}
      className="mx-3 mb-2 flex items-center gap-2 rounded-xl bg-background/70 px-3 py-2 ring-1 ring-border"
    >
      <MapPin aria-hidden="true" className="size-4 shrink-0 text-primary" />
      <label htmlFor={id} className="sr-only">
        {t("branch")}
      </label>
      <select
        id={id}
        name="branch_id"
        defaultValue={current ?? ""}
        disabled={pending}
        onChange={(event) => event.currentTarget.form?.requestSubmit()}
        className="min-w-0 flex-1 cursor-pointer truncate bg-transparent text-sm font-medium outline-none disabled:opacity-60"
      >
        <option value="">{t("allBranches")}</option>
        {branches.map((branch) => (
          <option key={branch.id} value={branch.id}>
            {branch.name}
          </option>
        ))}
      </select>
    </form>
  );
}
