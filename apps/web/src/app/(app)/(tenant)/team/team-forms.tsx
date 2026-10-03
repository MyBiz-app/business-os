"use client";

import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { Field, SelectField } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { changeRole, inviteMember, removeMember, type TeamState } from "./actions";

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
            <input readOnly value={state.link} dir="ltr" aria-label={t("copy")} className="min-w-0 flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm" />
            <button
              type="button"
              onClick={async () => {
                await navigator.clipboard.writeText(state.link ?? "");
                setCopied(true);
              }}
              className="rounded-lg border border-border px-3 py-2 text-sm font-medium"
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
  role: (typeof ROLES)[number];
  customRoleId: string | null;
  isSelf: boolean;
  allowOwner: boolean;
  customRoles: CustomRoleOption[];
};

export function MemberRow({ userId, email, role, customRoleId, isSelf, allowOwner, customRoles }: MemberRowProps) {
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
    <li className="flex flex-col gap-2 border-t border-border px-4 py-3 first:border-t-0">
      <TeamError state={roleState.error ? roleState : removeState} />
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex-1 truncate" dir="ltr">
          {email} {isSelf && <span className="text-muted">{t("team.you")}</span>}
        </span>
        <form action={roleAction}>
          <select
            name="role"
            key={current}
            defaultValue={current}
            disabled={roleLocked}
            aria-label={`${t("team.role")}: ${email}`}
            onChange={(event) => event.currentTarget.form?.requestSubmit()}
            className="rounded-lg border border-border bg-background px-2 py-1.5 text-sm"
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
