"use server";

import { revalidatePath } from "next/cache";

import { ApiError, unwrap } from "@/lib/api";
import { siteOrigin } from "@/lib/origin";
import { getTenant } from "@/lib/tenant";

type Role = "owner" | "manager" | "staff" | "front_desk";
const TEAM_ERRORS = ["already_member", "last_owner", "only_owners_manage_owners", "cannot_remove_self"] as const;
export type TeamError = (typeof TEAM_ERRORS)[number] | "invalid" | "generic";
export type TeamState = { error?: TeamError; link?: string; email?: string };

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
        body: { role: String(formData.get("role")) as Role },
      }),
    );
  } catch (error) {
    return { error: toError(error) };
  }
  revalidatePath("/team");
  return {};
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
