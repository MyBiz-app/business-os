"use server";

import { redirect } from "next/navigation";

import { clearActiveTenant, setActiveTenant } from "@/lib/tenant";

/** Opens a business that granted support access (the API checks the grant on every request). */
export async function openAsSupport(tenantId: string): Promise<void> {
  await setActiveTenant(tenantId);
  redirect("/dashboard");
}

export async function leaveSupport(): Promise<void> {
  await clearActiveTenant();
  redirect("/platform");
}
