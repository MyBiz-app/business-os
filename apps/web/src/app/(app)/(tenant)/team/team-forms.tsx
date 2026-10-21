"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { Ellipsis, UserPlus } from "lucide-react";
import { type ReactNode, useActionState, useEffect, useMemo, useRef, useState } from "react";

import { Avatar } from "@/components/avatar";
import { Field, SelectField } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { IdentityEditor } from "@/components/identity-editor";
import { Modal } from "@/components/ui/modal";
import { PermissionList } from "@/components/permission-list";
import { CardTransition } from "@/components/ui/page-transition";
import { SubmitButton } from "@/components/form/submit-button";

import { changeRole, inviteMember, removeMember, setBranches, type TeamState } from "./actions";

const ROLES = ["owner", "manager", "front_desk", "staff"] as const;
// A branch manager is appointed from the branch's page; here it only shows for someone who is one.
type TeamRole = (typeof ROLES)[number] | "branch_manager";

export type CustomRoleOption = { id: string; name: string };

function useRoleOptions(allowOwner: boolean, custom: CustomRoleOption[] = [], branchManager = false) {
  const t = useTranslations("roles");
  return [
    ...ROLES.filter((role) => allowOwner || role !== "owner").map((value) => ({ value: value as string, label: t(value) })),
    ...(branchManager ? [{ value: "branch_manager", label: t("branch_manager") }] : []),
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
  /** Where the name and "open" go: the card as a window over the list (`/team?open=<id>`). */
  openHref?: string;
  userId: string;
  allPermissions: string[];
  permissions: string[];
  email: string;
  name: string | null;
  role: TeamRole;
  customRoleId: string | null;
  isSelf: boolean;
  allowOwner: boolean;
  customRoles: CustomRoleOption[];
  /** The business's active branches (a picker appears when there are several). */
  branches: { id: string; name: string }[];
  memberBranches: string[];
  homeBranch?: string | null;
  avatar?: string | null;
  title?: string | null;
};

type Panel = "branches" | "permissions" | "identity" | "role";

/** One person in the list: a click on the row opens their card; everything else (role, branches,
 * permissions, ID number, removal) lives in the "..." menu so the row stays calm. */
export function MemberRow({ userId, email, name, role, customRoleId, isSelf, allowOwner, customRoles, branches, memberBranches, homeBranch = null, avatar = null, title = null, allPermissions, permissions, openHref }: MemberRowProps) {
  const t = useTranslations();
  const [removeState, removeAction] = useActionState<TeamState, FormData>(removeMember.bind(null, userId), {});
  const [roleState, roleAction] = useActionState<TeamState, FormData>(changeRole.bind(null, userId), {});
  const [panel, setPanel] = useState<Panel | null>(null);
  // A manager sees owners read-only; only owners can change or remove them.
  const locked = role === "owner" && !allowOwner;
  // Only owners may change their own role (to step down); nobody else can.
  const roleLocked = locked || (isSelf && !allowOwner);
  const roleOptions = useRoleOptions(allowOwner || role === "owner", role === "owner" ? [] : customRoles, role === "branch_manager");
  const current = customRoleId ? `custom:${customRoleId}` : role;
  const roleLabel = roleOptions.find((option) => option.value === current)?.label ?? role;
  const label = name ?? email;
  const removeForm = `remove-${userId}`;

  return (
    <CardTransition name={`member-${userId}`}>
      <li className="relative flex flex-col gap-2 border-t border-border px-5 py-4 transition-colors first:border-t-0 hover:bg-primary/4">
        <TeamError state={removeState.error ? removeState : roleState} />
        <div className="flex items-center gap-3">
          <Avatar id={userId} name={label} src={avatar} />
          <span className="flex min-w-0 flex-1 flex-col">
            {/* The link stretches over the whole row; the menu sits above it. */}
            <Link scroll={false} href={openHref ?? `/team/${userId}`} className="w-fit max-w-full truncate font-medium after:absolute after:inset-0 hover:text-primary-ink" dir="auto">
              {label} {isSelf && <span className="font-normal text-muted">{t("team.you")}</span>}
            </Link>
            <span className="truncate text-sm text-muted" dir="auto">
              {title ?? (name ? email : "")}
            </span>
          </span>
          <span className="hidden shrink-0 rounded-full bg-surface-2 px-3 py-1 text-xs font-medium text-muted sm:inline">{roleLabel}</span>
          <RowMenu label={t("team.moreActions", { name: label })}>
            {(close) => (
              <>
                {!roleLocked && <MenuItem onClick={() => { close(); setPanel("role"); }}>{t("team.changeRole")}</MenuItem>}
                {branches.length > 1 && <MenuItem onClick={() => { close(); setPanel("branches"); }}>{t("team.branchesMenu")}</MenuItem>}
                <MenuItem onClick={() => { close(); setPanel("permissions"); }}>{t("team.viewPermissions")}</MenuItem>
                <MenuItem onClick={() => { close(); setPanel("identity"); }}>{t("identity.title")}</MenuItem>
                {!isSelf && !locked && (
                  <MenuItem
                    danger
                    onClick={() => {
                      close();
                      if (window.confirm(t("team.removeConfirm", { email }))) (document.getElementById(removeForm) as HTMLFormElement | null)?.requestSubmit();
                    }}
                  >
                    {t("team.remove")}
                  </MenuItem>
                )}
              </>
            )}
          </RowMenu>
        </div>
        {!isSelf && !locked && <form id={removeForm} action={removeAction} hidden />}
        {panel === "role" && (
          <Modal size="sm" title={t("team.role")} description={label} onClose={() => setPanel(null)}>
            <form action={roleAction}>
              <select
                name="role"
                key={current}
                defaultValue={current}
                disabled={roleLocked}
                aria-label={`${t("team.role")}: ${email}`}
                onChange={(event) => {
                  event.currentTarget.form?.requestSubmit();
                  setPanel(null);
                }}
                className="control w-full px-2 py-2 text-sm"
              >
                {roleOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </form>
          </Modal>
        )}
        {panel === "branches" && <MemberBranches userId={userId} email={email} branches={branches} selected={memberBranches} home={homeBranch} onClose={() => setPanel(null)} />}
        {panel === "permissions" && <MemberPermissions email={email} all={allPermissions} allowed={permissions} onClose={() => setPanel(null)} />}
        {panel === "identity" && <MemberIdentity userId={userId} name={label} onClose={() => setPanel(null)} />}
      </li>
    </CardTransition>
  );
}

/** The "..." button and its small menu; closes on a click outside, on Esc and after a choice. */
function RowMenu({ label, children }: { label: string; children: (close: () => void) => ReactNode }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (event: PointerEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    const esc = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  return (
    <div ref={box} className="relative z-10 shrink-0">
      <button type="button" aria-label={label} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)} className="btn-ghost size-9 justify-center p-0">
        <Ellipsis aria-hidden="true" className="size-5" />
      </button>
      {open && (
        <div role="menu" className="card absolute end-0 top-full z-20 mt-1 flex min-w-48 flex-col p-1 shadow-lg">
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

function MenuItem({ children, onClick, danger = false }: { children: ReactNode; onClick: () => void; danger?: boolean }) {
  return (
    <button type="button" role="menuitem" onClick={onClick} className={`btn-plain rounded-lg px-3 py-2 text-start text-sm transition-colors hover:bg-surface-2 ${danger ? "text-danger" : ""}`}>
      {children}
    </button>
  );
}

/** The "Invite" button in the page header and the window with the form. */
export function InviteButton({ allowOwner }: { allowOwner: boolean }) {
  const t = useTranslations("team");
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="btn-primary px-4 py-2 text-sm" onClick={() => setOpen(true)}>
        <UserPlus aria-hidden="true" className="size-4" />
        {t("inviteButton")}
      </button>
      {open ? (
        <Modal size="sm" title={t("invite")} onClose={() => setOpen(false)}>
          <InviteForm allowOwner={allowOwner} />
        </Modal>
      ) : null}
    </>
  );
}

type MemberBranchesProps = { userId: string; email: string; branches: { id: string; name: string }[]; selected: string[]; home: string | null; onClose: () => void };

/** Where a member works: some branches, or (none checked) all of them. */
function MemberBranches({ userId, email, branches, selected, home, onClose }: MemberBranchesProps) {
  const t = useTranslations("team");
  const [state, action] = useActionState<TeamState, FormData>(setBranches.bind(null, userId), {});
  return (
    <Modal size="sm" title={t("branchesOf", { email })} onClose={onClose}>
      <form action={action} className="flex flex-col gap-3">
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
        <label className="flex flex-col gap-1 text-xs text-muted">
          {t("homeBranch")}
          <select name="home_location_id" defaultValue={home ?? ""} className="control px-2 py-1.5 text-sm text-foreground">
            <option value="">{t("noHomeBranch")}</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn-primary px-3 py-1.5 text-sm">
          {t("saveBranches")}
        </button>
      </form>
    </Modal>
  );
}

/** What a member can actually do, so an owner can check before (or after) changing their role. */
function MemberPermissions({ email, all, allowed, onClose }: { email: string; all: string[]; allowed: string[]; onClose: () => void }) {
  const t = useTranslations("team");
  return (
    <Modal size="sm" title={t("permissionsOf", { email })} onClose={onClose}>
      <div className="flex flex-col gap-3">
        <PermissionList all={all} allowed={allowed} />
        <p className="text-xs text-muted">{t("permissionsHint")}</p>
        <Link href="/team/roles" className="text-sm text-primary-ink underline-offset-4 hover:underline">
          {t("manageRoles")}
        </Link>
      </div>
    </Modal>
  );
}

/** The member's ID number (payroll and forms): masked, revealed only to those allowed, and loaded
 * only while the window is open. */
function MemberIdentity({ userId, name, onClose }: { userId: string; name: string; onClose: () => void }) {
  const t = useTranslations("identity");
  const subject = useMemo(() => ({ kind: "member" as const, id: userId }), [userId]);
  return (
    <Modal size="sm" title={t("title")} description={t("memberIntro", { name })} onClose={onClose}>
      <IdentityEditor subject={subject} />
    </Modal>
  );
}
