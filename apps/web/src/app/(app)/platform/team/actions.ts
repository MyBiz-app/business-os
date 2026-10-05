"use server";

import { revalidatePath } from "next/cache";

import { getPlatform, PLATFORM_PERMISSIONS, type PlatformPermission } from "@/lib/platform";

export type StaffState = { error?: string; saved?: boolean };

const KNOWN = new Set([
  "primary_owner_protected",
  "not_yourself",
  "cannot_grant_more_than_you_hold",
  "employees_do_not_manage_staff",
  "forbidden",
]);

async function errorOf(response: Response): Promise<StaffState> {
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const detail = typeof body?.detail === "string" ? body.detail : "";
  return { error: KNOWN.has(detail) ? detail : "generic" };
}

/** Adds a team member or changes one (the database enforces who may do what). */
export async function saveStaff(_state: StaffState, formData: FormData): Promise<StaffState> {
  const { api } = await getPlatform();
  const email = String(formData.get("email") ?? "").trim();
  const level = String(formData.get("level") ?? "employee") as "owner" | "manager" | "employee";
  const permissions = formData
    .getAll("permissions")
    .map(String)
    .filter((p): p is PlatformPermission => (PLATFORM_PERMISSIONS as string[]).includes(p));
  const { response } = await api.PUT("/platform/staff/{email}", {
    params: { path: { email } },
    body: { level, permissions, disabled: formData.get("disabled") === "on" },
  });
  if (!response.ok) return response.status === 422 && !email ? { error: "generic" } : errorOf(response);
  revalidatePath("/platform/team");
  return { saved: true };
}

export async function removeStaff(email: string): Promise<StaffState> {
  const { api } = await getPlatform();
  const { response } = await api.DELETE("/platform/staff/{email}", { params: { path: { email } } });
  if (!response.ok) return errorOf(response);
  revalidatePath("/platform/team");
  return { saved: true };
}

export async function setPaused(email: string, level: string, permissions: string[], paused: boolean): Promise<StaffState> {
  const { api } = await getPlatform();
  const { response } = await api.PUT("/platform/staff/{email}", {
    params: { path: { email } },
    body: { level: level as "employee", permissions: permissions as PlatformPermission[], disabled: paused },
  });
  if (!response.ok) return errorOf(response);
  revalidatePath("/platform/team");
  return { saved: true };
}

