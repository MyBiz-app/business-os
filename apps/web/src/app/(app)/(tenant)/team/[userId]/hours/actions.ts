"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

export type Block = { weekday: number; starts: string; ends: string };
export type HoursState = { saved?: boolean; error?: "overlapping_hours" | "invalid" | "generic" };

export async function saveHours(userId: string, blocks: Block[]): Promise<HoursState> {
  if (blocks.some((block) => !block.starts || !block.ends || block.ends <= block.starts)) {
    return { error: "invalid" };
  }
  const { api, scope } = await getTenantFor("schedule.write");
  const { response, error } = await api.PUT("/staff/{user_id}/hours", {
    params: { ...scope, path: { user_id: userId } },
    body: blocks,
  });
  if (!response.ok) {
    const detail = (new ApiError(response.status, error).body as { detail?: unknown } | null)?.detail;
    return { error: detail === "overlapping_hours" ? "overlapping_hours" : response.status === 422 ? "invalid" : "generic" };
  }
  revalidatePath(`/team/${userId}/hours`);
  return { saved: true };
}
