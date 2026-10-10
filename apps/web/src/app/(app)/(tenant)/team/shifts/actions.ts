"use server";

import { revalidatePath } from "next/cache";

import { getTenantFor } from "@/lib/tenant";
import { zonedToIso } from "@/lib/zoned";

export type ShiftState = { error?: "shift_overlap" | "invalid" | "generic"; saved?: boolean };

function fields(formData: FormData, timeZone: string) {
  const value = (name: string) => String(formData.get(name) ?? "");
  const day = value("day");
  const starts = zonedToIso(day, value("starts"), timeZone);
  // A shift ending at or before it starts runs past midnight.
  let ends = zonedToIso(day, value("ends"), timeZone);
  if (ends <= starts) ends = new Date(new Date(ends).getTime() + 24 * 3600 * 1000).toISOString();
  return {
    user_id: value("user_id"),
    location_id: value("location_id"),
    starts_at: starts,
    ends_at: ends,
    position: value("position"),
    note: value("note"),
  };
}

function failure(status: number, error: unknown): ShiftState {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (detail === "shift_overlap") return { error: "shift_overlap" };
  return { error: status === 422 ? "invalid" : "generic" };
}

/** Plans a shift, or changes one (`shiftId`). Times are the business's local times. */
export async function saveShift(shiftId: string | null, _state: ShiftState, formData: FormData): Promise<ShiftState> {
  const { api, scope, tenant } = await getTenantFor("staff.manage");
  let body;
  try {
    body = fields(formData, tenant.time_zone);
  } catch {
    return { error: "invalid" };
  }
  const { response, error } = shiftId
    ? await api.PATCH("/shifts/{shift_id}", { params: { ...scope, path: { shift_id: shiftId } }, body })
    : await api.POST("/shifts", { params: scope, body });
  if (!response.ok) return failure(response.status, error);
  revalidatePath("/team/shifts");
  revalidatePath("/schedule");
  return { saved: true };
}

export async function deleteShift(shiftId: string): Promise<void> {
  const { api, scope } = await getTenantFor("staff.manage");
  await api.DELETE("/shifts/{shift_id}", { params: { ...scope, path: { shift_id: shiftId } } });
  revalidatePath("/team/shifts");
  revalidatePath("/schedule");
}

export type CopyState = { copied?: { created: number; skipped: number }; error?: boolean };

export async function copyShiftsWeek(from: string, to: string): Promise<CopyState> {
  const { api, scope } = await getTenantFor("staff.manage");
  const { data } = await api.POST("/shifts/copy-week", { params: scope, body: { from_week: from, to_week: to } });
  if (!data) return { error: true };
  revalidatePath("/team/shifts");
  return { copied: data };
}
