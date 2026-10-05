"use server";

import { revalidatePath } from "next/cache";

import { ApiError, unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
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

export async function addTimeOff(userId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenantFor("schedule.write");
  const value = (name: string) => String(formData.get(name) ?? "");
  try {
    unwrap(
      await api.POST("/staff/{user_id}/time-off", {
        params: { ...scope, path: { user_id: userId } },
        body: { starts_on: value("starts_on"), ends_on: value("ends_on") || value("starts_on"), reason: value("reason") || null },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/team/${userId}/hours`);
  return { saved: true };
}

export async function removeTimeOff(userId: string, timeOffId: string): Promise<void> {
  const { api, scope } = await getTenantFor("schedule.write");
  const { response } = await api.DELETE("/staff/{user_id}/time-off/{time_off_id}", {
    params: { ...scope, path: { user_id: userId, time_off_id: timeOffId } },
  });
  if (!response.ok) throw new ApiError(response.status, "remove time off failed");
  revalidatePath(`/team/${userId}/hours`);
}
