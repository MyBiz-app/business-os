"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { getApi, unwrap } from "@/lib/api";
import { getActiveMembership, getTenant } from "@/lib/tenant";

export type ClosureState = { error?: "name_mismatch" | "already_closed" | "owner_only" | "generic" };

/** The owner closes the business after typing its exact name (the API checks it again). */
export async function closeBusiness(_state: ClosureState, formData: FormData): Promise<ClosureState> {
  const { api, scope } = await getTenant();
  const result = await api.POST("/tenants/current/closure", {
    params: scope,
    body: { confirm_name: String(formData.get("confirm_name") ?? "") },
  });
  if (result.error) {
    const detail = (result.error as { detail?: string }).detail;
    return { error: detail === "name_mismatch" || detail === "already_closed" || detail === "owner_only" ? detail : "generic" };
  }
  revalidatePath("/", "layout");
  redirect("/closed");
}

/** The owner reopens a closed business within the 90 days. */
export async function reopenBusiness(): Promise<void> {
  const { membership } = await getActiveMembership();
  if (!membership) redirect("/welcome");
  const api = await getApi();
  unwrap(await api.DELETE("/tenants/current/closure", { params: { header: { "X-Tenant-Id": membership.tenant_id } } }));
  revalidatePath("/", "layout");
  redirect("/dashboard");
}
