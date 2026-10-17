"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api";
import type { Block, HoursState } from "@/lib/hours";
import { getTenantFor } from "@/lib/tenant";

/** Replaces the weekly availability of a team member; an empty week means "no limit". */
export async function saveAvailability(userId: string, blocks: Block[]): Promise<HoursState> {
  if (blocks.some((block) => !block.starts || !block.ends || block.ends <= block.starts)) {
    return { error: "invalid" };
  }
  const { api, scope } = await getTenantFor("staff.manage");
  const { response, error } = await api.PUT("/staff/{user_id}/availability", {
    params: { ...scope, path: { user_id: userId } },
    body: { windows: blocks },
  });
  if (!response.ok) {
    const detail = JSON.stringify((new ApiError(response.status, error).body as { detail?: unknown } | null)?.detail ?? "");
    return { error: response.status === 422 ? (detail.includes("overlap") ? "overlapping_hours" : "invalid") : "generic" };
  }
  revalidatePath(`/team/${userId}`);
  revalidatePath("/team/shifts");
  return { saved: true };
}
