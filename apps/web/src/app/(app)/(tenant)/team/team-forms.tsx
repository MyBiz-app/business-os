"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState, useState } from "react";

import { Avatar } from "@/components/avatar";
import { Field, SelectField } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { changeRole, inviteMember, removeMember, setBranches, type TeamState } from "./actions";

const ROLES = ["owner", "manager", "front_desk", "staff"] as const;

export type CustomRoleOption = { id: string; name: string };

function useRoleOptions(allowOwner: boolean, custom: CustomRoleOption[] = []) {
  const t = useTranslations("roles");
  return [
    ...ROLES.filter((role) => allowOwner || role !== "owner").map((value) => ({ value: value as string, label: t(value) })),
    ...custom.map((role) => ({ value: `custom:${role.id}`, label: role.name })),
  ];
}

function TeamError({ state }: { state: TeamState }) {
  const t = useTranslations("team.errors");
  return <FormError message={state.error && t(state.error)} />;
}

export function InviteForm({ allowOwner }: { allowOwner: boolean }) {
  const t = useTranslations("team");
  const [state, action] = useActionState<TeamState, FormData>(inviteMember, {});
  const [copied, setCopied] = useState(false);
  const roleOptions = useRoleOptions(allowOwner);

  return (
    <div className="flex flex-col gap-4">
      <form action={action} className="flex flex-col gap-4">
        <TeamError state={state} />
        <div className="grid gap-4 sm:grid-cols-[1fr_12rem]">
          <Field label={t("email")} name="email" type="email" dir="ltr" required defaultValue={state.link ? "" : state.email} />
          <SelectField label={t("role")} name="role" defaultValue="staff" options={roleOptions} />
        </div>
        <div>
          <SubmitButton>{t("inviteSubmit")}</SubmitButton>
        </div>
      </form>
      {state.link && (
        <div className="flex flex-col gap-2">
          <FormNotice message={t("inviteCreated", { email: state.email ?? "" })} />
          <div className="flex gap-2">
            <input readOnly value={state.link} dir="ltr" aria-label={t("copy")} className="min-w-0 flex-1 control px-3 py-2 text-sm" />
            <button
              type="button"
              onClick={async () => {
                await navigator.clipboard.writeText(state.link ?? "");
                setCopied(true);
              }}
              className="btn-secondary px-3 py-2 text-sm"
            >
              {copied ? t("copied") : t("copy")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

type MemberRowProps = {
  userId: string;
  email: string;
  name: string | null;
  role: (typeof ROLES)[number];
  customRoleId: string | null;
  isSelf: boolean;
  allowOwner: boolean;
  customRoles: CustomRoleOption[];
  /** The business's active branches (a picker appears when there are several). */
  branches: { id: string; name: string }[];
  memberBranches: string[];
};

export function MemberRow({ userId, email, name, role, customRoleId, isSelf, allowOwner, customRoles, branches, memberBranches }: MemberRowProps) {
  const t = useTranslations();
  const [roleState, roleAction] = useActionState<TeamState, FormData>(changeRole.bind(null, userId), {});
  const [removeState, removeAction] = useActionState<TeamState, FormData>(removeMember.bind(null, userId), {});
  // A manager sees owners read-only; only owners can change or remove them.
  const locked = role === "owner" && !allowOwner;
  // Only owners may change their own role (to step down); nobody else can.
  const roleLocked = locked || (isSelf && !allowOwner);
  const roleOptions = useRoleOptions(allowOwner || role === "owner", role === "owner" ? [] : customRoles);
  const current = customRoleId ? `custom:${customRoleId}` : role;

  return (
    <li className="flex flex-col gap-2 border-t border-border px-5 py-4 transition-colors first:border-t-0 hover:bg-primary/4">
      <TeamError state={roleState.error ? roleState : removeState} />
      <div className="flex flex-wrap items-center gap-3">
        <Avatar id={userId} name={name ?? email} />
        {/* The name keeps its own line on phones; the actions wrap below it. */}
        <span className="flex min-w-48 flex-1 flex-col">
          <span className="truncate font-medium" dir="auto">
            {name ?? email} {isSelf && <span className="font-normal text-muted">{t("team.you")}</span>}
          </span>
          {name && (
            <span className="truncate text-sm text-muted" dir="ltr">
              {email}
            </span>
          )}
        </span>
        {branches.length > 1 && <MemberBranches userId={userId} email={email} branches={branches} selected={memberBranches} />}
        <Link href={`/team/${userId}/hours`} className="btn-secondary px-3 py-1.5 text-sm">
          {t("hours.link")}
        </Link>
        <form action={roleAction}>
          <select
            name="role"
            key={current}
            defaultValue={current}
            disabled={roleLocked}
            aria-label={`${t("team.role")}: ${email}`}
            onChange={(event) => event.currentTarget.form?.requestSubmit()}
            className="control px-2 py-1.5 text-sm"
          >
            {roleOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </form>
        {!isSelf && !locked && (
          <form
            action={removeAction}
            onSubmit={(event) => {
              if (!window.confirm(t("team.removeConfirm", { email }))) event.preventDefault();
            }}
          >
            <button type="submit" className="text-sm text-danger underline-offset-4 hover:underline">
              {t("team.remove")}
            </button>
          </form>
        )}
      </div>
    </li>
  );
}

type MemberBranchesProps = { userId: string; email: string; branches: { id: string; name: string }[]; selected: string[] };

/** Where a member works: some branches, or (none checked) all of them. */
function MemberBranches({ userId, email, branches, selected }: MemberBranchesProps) {
  const t = useTranslations("team");
  const [state, action] = useActionState<TeamState, FormData>(setBranches.bind(null, userId), {});
  const names = branches.filter((b) => selected.includes(b.id)).map((b) => b.name);
  return (
    <details className="group relative">
      <summary className="control cursor-pointer list-none px-2 py-1.5 text-sm [&::-webkit-details-marker]:hidden">
        <span className="sr-only">{t("branchesOf", { email })}: </span>
        {names.length === 0 ? t("allBranches") : names.length === 1 ? names[0] : t("someBranches", { count: names.length })}
      </summary>
      <form action={action} className="absolute end-0 top-full z-20 mt-1 flex w-56 flex-col gap-2 rounded-2xl bg-surface p-3 shadow-xl ring-1 ring-border">
        <TeamError state={state} />
        <fieldset className="flex flex-col gap-1.5">
          <legend className="mb-1 text-xs text-muted">{t("branchesHint")}</legend>
          {branches.map((branch) => (
            <label key={branch.id} className="flex items-center gap-2 text-sm">
              <input type="checkbox" name="location_ids" value={branch.id} defaultChecked={selected.includes(branch.id)} className="size-4 accent-primary" />
              <span dir="auto">{branch.name}</span>
            </label>
          ))}
        </fieldset>
        <button type="submit" className="btn-primary px-3 py-1.5 text-sm">
          {t("saveBranches")}
        </button>
      </form>
    </details>
  );
}
