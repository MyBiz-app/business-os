"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { deleteRole, saveRole, type TeamState } from "../actions";

type PermissionKey = "clients_read" | "clients_write" | "catalog_read" | "catalog_write" | "schedule_read"
  | "schedule_write" | "bookings_manage" | "sales_manage" | "reports_read" | "ai_use" | "staff_read"
  | "staff_manage" | "business_settings";
const key = (permission: string) => permission.replace(".", "_") as PermissionKey;

type Props = {
  role?: { id: string; name: string; permissions: string[]; members: number };
  /** Every permission key, grouped for display. */
  permissions: string[];
  /** Keys the current user may hand out (their own). */
  grantable: string[];
};

export function RoleForm({ role, permissions, grantable }: Props) {
  const t = useTranslations();
  const [state, action] = useActionState<TeamState, FormData>(saveRole.bind(null, role?.id ?? null), {});
  const [removed, remove] = useActionState<TeamState, FormData>(deleteRole.bind(null, role?.id ?? ""), {});
  const error = state.error ?? removed.error;

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-5">
      <form action={action} className="flex flex-col gap-4" key={state.created ? "created" : (role?.id ?? "new")}>
        <FormError message={error && t(`team.errors.${error}`)} />
        <Field label={t("team.roleName")} name="name" required maxLength={60} defaultValue={role?.name ?? ""} />
        <fieldset className="grid gap-2 sm:grid-cols-2">
          <legend className="mb-1 text-sm font-medium">{t("team.rolePermissions")}</legend>
          {permissions.map((permission) => {
            const allowed = grantable.includes(permission);
            return (
              <label key={permission} className={`flex items-start gap-2 text-sm ${allowed ? "" : "opacity-60"}`}>
                <input
                  type="checkbox"
                  name="permissions"
                  value={permission}
                  defaultChecked={role?.permissions.includes(permission)}
                  disabled={!allowed && !role?.permissions.includes(permission)}
                  className="mt-0.5 size-4 accent-[var(--primary)]"
                />
                <span className="flex flex-col">
                  <span className="font-medium">{t(`permissions.${key(permission)}`)}</span>
                  <span className="text-xs text-muted">{t(`permissions.${key(permission)}_hint` as `permissions.${PermissionKey}_hint`)}</span>
                </span>
              </label>
            );
          })}
        </fieldset>
        <div className="flex items-center gap-4">
          <SubmitButton>{role ? t("common.save") : t("common.create")}</SubmitButton>
          {state.created && <FormNotice message={t("team.roleCreated")} />}
        </div>
      </form>
      {role && (
        <form
          action={remove}
          onSubmit={(event) => {
            if (!window.confirm(t("team.deleteRoleConfirm", { name: role.name }))) event.preventDefault();
          }}
          className="flex items-center gap-3 border-t border-border pt-3"
        >
          <span className="flex-1 text-sm text-muted">{t("team.roleMembers", { count: role.members })}</span>
          <button type="submit" className="text-sm text-danger underline-offset-4 hover:underline">
            {t("team.deleteRole")}
          </button>
        </form>
      )}
    </div>
  );
}
