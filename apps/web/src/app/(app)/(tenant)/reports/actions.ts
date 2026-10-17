"use server";

import { redirect } from "next/navigation";

import { getActiveMembership, setActiveBranch } from "@/lib/tenant";

/** From a branch in the comparison to the dashboard looking at that branch only. */
export async function openBranchDashboard(formData: FormData): Promise<void> {
  const { membership } = await getActiveMembership();
  if (!membership) return;
  // The API re-checks that the person may see this branch on every request.
  await setActiveBranch(membership.tenant_id, String(formData.get("branch_id") ?? "") || null);
  redirect("/dashboard");
}
