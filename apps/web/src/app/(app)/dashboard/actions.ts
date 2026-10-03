"use server";

import { redirect } from "next/navigation";

import { setActiveTenant } from "@/lib/tenant";

export async function switchBusiness(formData: FormData): Promise<void> {
  // The API re-checks membership on every request, so an invalid id cannot grant access.
  await setActiveTenant(String(formData.get("tenant_id") ?? ""));
  redirect("/dashboard");
}
