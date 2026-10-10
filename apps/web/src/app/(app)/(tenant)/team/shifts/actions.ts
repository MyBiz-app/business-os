"use server";

import { revalidatePath } from "next/cache";

import { addDays } from "@/lib/dates";
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

/** Repeats the week starting `from` over the `weeks` weeks that follow it. */
export async function copyShiftsWeek(from: string, weeks: number): Promise<CopyState> {
  const { api, scope } = await getTenantFor("staff.manage");
  const { data } = await api.POST("/shifts/copy-week", { params: scope, body: { from_week: from, to_week: addDays(from, 7), repeat: weeks } });
  if (!data) return { error: true };
  revalidatePath("/team/shifts");
  return { copied: data };
}

/** Repeats a day's shifts on the `days` days that follow it. */
export async function copyShiftsDay(from: string, days: number): Promise<CopyState> {
  const { api, scope } = await getTenantFor("staff.manage");
  const { data } = await api.POST("/shifts/copy-day", { params: scope, body: { from_day: from, to_days: Array.from({ length: days }, (_, i) => addDays(from, i + 1)) } });
  if (!data) return { error: true };
  revalidatePath("/team/shifts");
  return { copied: data };
}

export type PlanningState = { saved?: boolean; error?: boolean };

/** How often a branch plans its shifts (sets the window its board opens on). */
export async function savePlanning(locationId: string, _state: PlanningState, formData: FormData): Promise<PlanningState> {
  const { api, scope } = await getTenantFor("catalog.write");
  const cadence = String(formData.get("cadence") ?? "weekly") as "daily" | "weekly" | "monthly" | "custom";
  const days = Number(formData.get("days"));
  const { response } = await api.PUT("/locations/{location_id}/planning", {
    params: { ...scope, path: { location_id: locationId } },
    body: cadence === "custom" ? { cadence, days } : { cadence },
  });
  if (!response.ok) return { error: true };
  revalidatePath("/team/shifts");
  return { saved: true };
}

export type DefaultViewState = { saved?: boolean; error?: boolean };

/** The owner's choice of how the shifts board opens: people or branches, the range, the branches. */
export async function saveShiftsDefault(
  view: "people" | "branches",
  range: "day" | "week" | "month" | "custom",
  branches: string[],
  _state: DefaultViewState,
  _formData: FormData,
): Promise<DefaultViewState> {
  const { api, scope } = await getTenantFor("business.settings");
  const { error } = await api.PATCH("/tenants/current", {
    params: scope,
    body: { shifts_default_view: view, shifts_default_range: range, shifts_default_branches: branches },
  });
  if (error) return { error: true };
  revalidatePath("/team/shifts");
  return { saved: true };
}

export type TemplateState = { saved?: boolean; error?: "name_taken" | "invalid" | "generic" };

/** Saves a branch's named shift type (the times are the business's local times). */
export async function saveTemplate(locationId: string, name: string, starts: string, ends: string, position: string): Promise<TemplateState> {
  const { api, scope } = await getTenantFor("staff.manage");
  const { response, error } = await api.POST("/shift-templates", {
    params: scope,
    body: { location_id: locationId, name, starts, ends, position: position || null },
  });
  if (!response.ok) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    return { error: detail === "template_name_taken" ? "name_taken" : response.status === 422 ? "invalid" : "generic" };
  }
  revalidatePath("/team/shifts");
  return { saved: true };
}

export async function deleteTemplate(templateId: string): Promise<void> {
  const { api, scope } = await getTenantFor("staff.manage");
  await api.DELETE("/shift-templates/{template_id}", { params: { ...scope, path: { template_id: templateId } } });
  revalidatePath("/team/shifts");
}

export type CoverageRuleInput = { weekday: number; starts_minute: number; ends_minute: number; min_staff: number };
export type CoverageState = { saved?: boolean; error?: boolean };

/** Replaces a branch's coverage rules: the least people needed on shift per weekday and stretch. */
export async function saveCoverageRules(locationId: string, rules: CoverageRuleInput[]): Promise<CoverageState> {
  const { api, scope } = await getTenantFor("staff.manage");
  const { response } = await api.PUT("/locations/{location_id}/coverage-rules", {
    params: { ...scope, path: { location_id: locationId } },
    body: { rules },
  });
  if (!response.ok) return { error: true };
  revalidatePath("/team/shifts");
  return { saved: true };
}

export type PublishState = { published?: number; error?: boolean };

/** Makes the draft shifts of the visible stretch visible to the team. */
export async function publishShifts(start: string, days: number, branches: string[]): Promise<PublishState> {
  const { api, scope } = await getTenantFor("staff.manage");
  const { data } = await api.POST("/shifts/publish", { params: scope, body: { start, days, location_id: branches.length ? branches : null } });
  if (!data) return { error: true };
  revalidatePath("/team/shifts");
  revalidatePath("/schedule");
  return { published: data.published };
}

export type PublishingState = { saved?: boolean; error?: boolean };

/** How the roster goes out: automatically or by hand, how often, on which day, at what time. */
export async function savePublishing(_state: PublishingState, formData: FormData): Promise<PublishingState> {
  const { api, scope } = await getTenantFor("business.settings");
  const cadence = String(formData.get("cadence") ?? "weekly") as "daily" | "weekly" | "monthly";
  const { error } = await api.PATCH("/tenants/current", {
    params: scope,
    body: {
      shifts_publish_auto: formData.get("auto") === "on",
      shifts_publish_cadence: cadence,
      shifts_publish_weekday: Number(formData.get("weekday") ?? 6),
      shifts_publish_day: Number(formData.get("day") ?? 1),
      shifts_publish_time: String(formData.get("time") ?? "08:00"),
    },
  });
  if (error) return { error: true };
  revalidatePath("/team/shifts");
  return { saved: true };
}
