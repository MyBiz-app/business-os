"use server";

import { revalidatePath } from "next/cache";

import { getTenant } from "@/lib/tenant";

export type MemberAiInput = { ai_access: boolean | null; monthly_credits: number | null; daily_percent: number | null };
export type MemberAiResult = { ok: true } | { ok: false; error: "ai_users_full" | "owner_always_has_ai" | "invalid" | "generic" };

/** Saves a team member's AI settings: their own switch, monthly limit and daily pace. */
export async function saveMemberAi(userId: string, input: MemberAiInput): Promise<MemberAiResult> {
  const { api, scope } = await getTenant();
  const { error, response } = await api.PUT("/ai/members/{user_id}", { params: { ...scope, path: { user_id: userId } }, body: input });
  if (!error) {
    revalidatePath(`/team/${userId}`);
    return { ok: true };
  }
  const detail = (error as { detail?: unknown }).detail;
  if (detail === "ai_users_full" || detail === "owner_always_has_ai") return { ok: false, error: detail };
  return { ok: false, error: response.status === 422 ? "invalid" : "generic" };
}

