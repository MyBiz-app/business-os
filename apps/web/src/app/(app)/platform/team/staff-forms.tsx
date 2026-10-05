"use client";

import { Lock, Pause, Play, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useState, useTransition } from "react";

import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { removeStaff, saveStaff, setPaused, type StaffState } from "./actions";

type Level = "owner" | "manager" | "employee";
type Permission = "businesses.read" | "businesses.act" | "billing.manage" | "inbox.manage" | "usage.read" | "staff.manage";

export type Member = {
  email: string;
  level: "primary_owner" | Level;
  permissions: Permission[];
  disabled: boolean;
  full_name: string | null;
  signed_up: boolean;
};

/** Message keys can't contain dots: "businesses.read" → "businesses_read". */
const key = (permission: Permission) => permission.replace(".", "_") as "businesses_read";

type Actor = {
  /** Levels this person may give (owners: all three; managers: employee). */
  levels: Level[];
  /** Permissions this person holds (and so may give). */
  permissions: Permission[];
};

function useError() {
  const t = useTranslations("platform.team.errors");
  return (state: StaffState) => (state.error ? t(state.error as "generic") : undefined);
}

/** Level and permission switches; owners hold everything, so they have none to pick. */
function LevelAndPermissions({ actor, level: initialLevel, permissions }: { actor: Actor; level: Level; permissions: Permission[] }) {
  const t = useTranslations("platform");
  const [level, setLevel] = useState<Level>(initialLevel);
  const offered = actor.permissions.filter((p) => !(level === "employee" && p === "staff.manage"));
  return (
    <>
      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-medium">{t("team.level")}</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {actor.levels.map((value) => (
            <label
              key={value}
              className={`flex cursor-pointer flex-col gap-0.5 rounded-xl border p-3 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-primary ${
                level === value ? "border-primary bg-primary/10" : "border-border"
              }`}
            >
              <span className="flex items-center gap-2 font-semibold">
                <input type="radio" name="level" value={value} checked={level === value} onChange={() => setLevel(value)} className="accent-[var(--primary)]" />
                {t(`levels.${value}`)}
              </span>
              <span className="text-xs text-muted">{t(`levelHints.${value}`)}</span>
            </label>
          ))}
        </div>
      </fieldset>
      {level === "owner" ? (
        <p className="text-sm text-muted">{t("team.allPermissions")}</p>
      ) : (
        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium">{t("team.permissions")}</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {offered.map((permission) => (
              <label key={permission} className="flex items-start gap-2 rounded-xl border border-border p-3 text-sm">
                <input
                  type="checkbox"
                  name="permissions"
                  value={permission}
                  defaultChecked={permissions.includes(permission) || (level === "manager" && permission === "staff.manage" && permissions.length === 0)}
                  className="mt-0.5 size-4 accent-[var(--primary)]"
                />
                <span className="flex flex-col">
                  <span className="font-medium">{t(`permissions.${key(permission)}.name`)}</span>
                  <span className="text-xs text-muted">{t(`permissions.${key(permission)}.hint`)}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      )}
    </>
  );
}

export function AddStaffForm({ actor }: { actor: Actor }) {
  const t = useTranslations("platform.team");
  const error = useError();
  const [state, action] = useActionState<StaffState, FormData>(saveStaff, {});
  const [key, setKey] = useState(0);
  return (
    <form
      key={key}
      action={async (data) => {
        await action(data);
        setKey((k) => k + 1);
      }}
      className="flex flex-col gap-4"
    >
      <FormError message={error(state)} />
      <FormNotice message={state.saved ? t("added") : undefined} />
      <div className="flex flex-col gap-1.5">
        <label htmlFor="staff-email" className="text-sm font-medium">
          {t("email")}
        </label>
        <input id="staff-email" name="email" type="email" required dir="ltr" autoComplete="off" className="control w-full px-3 py-2" />
      </div>
      <LevelAndPermissions actor={actor} level={actor.levels.at(-1)!} permissions={[]} />
      <div>
        <SubmitButton>{t("save")}</SubmitButton>
      </div>
    </form>
  );
}

export function StaffRow({ member, actor, manageable }: { member: Member; actor: Actor; manageable: boolean }) {
  const t = useTranslations("platform");
  const error = useError();
  const [editing, setEditing] = useState(false);
  const [state, action] = useActionState<StaffState, FormData>(saveStaff, {});
  const [rowState, setRowState] = useState<StaffState>({});
  const [pending, startTransition] = useTransition();
  const name = member.full_name ?? member.email;

  return (
    <li className="flex flex-col gap-3 border-t border-border px-4 py-4 first:border-t-0">
      <FormError message={error(rowState)} />
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate font-medium" dir="auto">
            {name}
          </span>
          {member.full_name && (
            <span className="truncate text-sm text-muted" dir="ltr">
              {member.email}
            </span>
          )}
        </span>
        <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">{t(`levels.${member.level}`)}</span>
        {member.level === "primary_owner" && (
          <span className="flex items-center gap-1 text-xs text-muted">
            <Lock aria-hidden="true" className="size-3.5" />
            {t("team.protected")}
          </span>
        )}
        {member.disabled && <span className="rounded-full bg-warning/15 px-2.5 py-0.5 text-xs font-semibold">{t("team.paused")}</span>}
        {!member.signed_up && <span className="text-xs text-muted">{t("team.invited")}</span>}
      </div>
      {member.level !== "owner" && member.level !== "primary_owner" && member.permissions.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {member.permissions.map((p) => (
            <li key={p} className="rounded-lg bg-foreground/5 px-2 py-0.5 text-xs">
              {t(`permissions.${key(p)}.name`)}
            </li>
          ))}
        </ul>
      )}
      {manageable && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <button type="button" onClick={() => setEditing((v) => !v)} aria-expanded={editing} className="btn-secondary px-3 py-1.5">
            {t("team.level")} · {t("team.permissions")}
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={() =>
              startTransition(async () =>
                setRowState(await setPaused(member.email, member.level, member.permissions, !member.disabled)),
              )
            }
            className="btn-secondary px-3 py-1.5"
          >
            {member.disabled ? <Play aria-hidden="true" className="size-4" /> : <Pause aria-hidden="true" className="size-4" />}
            {member.disabled ? t("team.enable") : t("team.disable")}
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={() => {
              if (window.confirm(t("team.removeConfirm", { email: member.email }))) {
                startTransition(async () => setRowState(await removeStaff(member.email)));
              }
            }}
            className="flex items-center gap-1 rounded-lg px-3 py-1.5 font-medium text-danger hover:bg-danger/10"
          >
            <Trash2 aria-hidden="true" className="size-4" />
            {t("team.remove")}
          </button>
        </div>
      )}
      {manageable && editing && (
        <form action={action} className="flex flex-col gap-4 rounded-xl border border-border p-4">
          <FormError message={error(state)} />
          <FormNotice message={state.saved ? t("team.added") : undefined} />
          <input type="hidden" name="email" value={member.email} />
          {member.disabled && <input type="hidden" name="disabled" value="on" />}
          <LevelAndPermissions actor={actor} level={member.level as Level} permissions={member.permissions} />
          <div>
            <SubmitButton>{t("team.save")}</SubmitButton>
          </div>
        </form>
      )}
    </li>
  );
}
