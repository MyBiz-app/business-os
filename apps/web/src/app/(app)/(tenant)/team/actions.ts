"use server";

import { revalidatePath } from "next/cache";

import { ApiError, unwrap } from "@/lib/api";
import { siteOrigin } from "@/lib/origin";
import { getTenant } from "@/lib/tenant";

type Role = "owner" | "manager" | "staff" | "front_desk";
const TEAM_ERRORS = [
  "already_member",
  "last_owner",
  "only_owners_manage_owners",
  "cannot_remove_self",
  "cannot_change_own_role",
  "exceeds_own_permissions",
  "name_taken",
  "role_in_use",
] as const;
export type TeamError = (typeof TEAM_ERRORS)[number] | "invalid" | "generic";
export type TeamState = { error?: TeamError; link?: string; email?: string; created?: boolean };

function toError(error: unknown): TeamError {
  if (error instanceof ApiError) {
    const detail = (error.body as { detail?: unknown } | null)?.detail;
    const known = TEAM_ERRORS.find((code) => code === detail);
    if (known) return known;
    if (error.status === 422) return "invalid";
  }
  return "generic";
}

export async function inviteMember(_state: TeamState, formData: FormData): Promise<TeamState> {
  const { api, scope } = await getTenant();
  const email = String(formData.get("email") ?? "");
  try {
    const invitation = unwrap(
      await api.POST("/staff/invitations", {
        params: scope,
        body: { email, role: String(formData.get("role")) as Role },
      }),
    );
    revalidatePath("/team");
    return { link: `${await siteOrigin()}/invite/${invitation.token}`, email: invitation.email };
  } catch (error) {
    return { error: toError(error), email };
  }
}

export async function changeRole(userId: string, _state: TeamState, formData: FormData): Promise<TeamState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.PATCH("/staff/{user_id}", {
        params: { ...scope, path: { user_id: userId } },
        // "custom:<id>" assigns a custom role; anything else is a system role.
        body: assignment(String(formData.get("role"))),
      }),
    );
  } catch (error) {
    return { error: toError(error) };
  }
  revalidatePath("/team");
  return {};
}

/** The branches a member works at (none checked: all branches). */
export async function setBranches(userId: string, _state: TeamState, formData: FormData): Promise<TeamState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.PUT("/staff/{user_id}/branches", {
        params: { ...scope, path: { user_id: userId } },
        body: { location_ids: formData.getAll("location_ids").map(String) },
      }),
    );
  } catch (error) {
    return { error: toError(error) };
  }
  revalidatePath("/team");
  return {};
}

function assignment(value: string): { role: Role } | { custom_role_id: string } {
  return value.startsWith("custom:") ? { custom_role_id: value.slice("custom:".length) } : { role: value as Role };
}

export async function removeMember(userId: string, _state: TeamState): Promise<TeamState> {
  const { api, scope } = await getTenant();
  const { response, error } = await api.DELETE("/staff/{user_id}", {
    params: { ...scope, path: { user_id: userId } },
  });
  if (!response.ok) return { error: toError(new ApiError(response.status, error)) };
  revalidatePath("/team");
  return {};
}

export async function revokeInvitation(invitationId: string): Promise<void> {
  const { api, scope } = await getTenant();
  await api.DELETE("/staff/invitations/{invitation_id}", {
    params: { ...scope, path: { invitation_id: invitationId } },
  });
  revalidatePath("/team");
}

export async function saveRole(roleId: string | null, _state: TeamState, formData: FormData): Promise<TeamState> {
  const { api, scope } = await getTenant();
  const body = {
    name: String(formData.get("name") ?? ""),
    permissions: formData.getAll("permissions").map(String) as never,
  };
  try {
    if (roleId) {
      unwrap(await api.PATCH("/roles/{role_id}", { params: { ...scope, path: { role_id: roleId } }, body }));
    } else {
      unwrap(await api.POST("/roles", { params: scope, body }));
    }
  } catch (error) {
    return { error: toError(error) };
  }
  revalidatePath("/team", "layout");
  return roleId ? {} : { created: true };
}

export async function deleteRole(roleId: string, _state: TeamState): Promise<TeamState> {
  const { api, scope } = await getTenant();
  const { response, error } = await api.DELETE("/roles/{role_id}", {
    params: { ...scope, path: { role_id: roleId } },
  });
  if (!response.ok) return { error: toError(new ApiError(response.status, error)) };
  revalidatePath("/team", "layout");
  return {};
}
