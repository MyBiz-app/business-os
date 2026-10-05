"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { getActiveMembership, setActiveBranch, setActiveTenant } from "@/lib/tenant";

/** Opens another of the person's businesses. The API re-checks membership on every request,
 * so an invalid id cannot grant access. */
export async function switchBusiness(formData: FormData): Promise<void> {
  await setActiveTenant(String(formData.get("tenant_id") ?? ""));
  redirect("/dashboard");
}

/** Chooses the current branch of the open business ("" = all branches). */
export async function switchBranch(formData: FormData): Promise<void> {
  const { membership } = await getActiveMembership();
  if (!membership) return;
  const branch = String(formData.get("branch_id") ?? "");
  await setActiveBranch(membership.tenant_id, branch || null);
  revalidatePath("/", "layout");
}
