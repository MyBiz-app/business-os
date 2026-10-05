"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { getTenant, getTenantFor } from "@/lib/tenant";

const HOURS = 24;

export async function grantSupport(): Promise<void> {
  const { api, scope } = await getTenantFor("business.settings");
  unwrap(await api.POST("/support-access", { params: scope, body: { hours: HOURS } }));
  revalidatePath("/settings");
}

export async function revokeSupport(): Promise<void> {
  const { api, scope } = await getTenantFor("business.settings");
  unwrap(await api.DELETE("/support-access", { params: scope }));
  revalidatePath("/settings");
}

export type WriteState = { error?: "too_many_requests" | "generic"; sent?: boolean };

/** A question or complaint from the business to the MyBiz team (the console's inbox). */
export async function writeToMyBiz(_state: WriteState, formData: FormData): Promise<WriteState> {
  const { api, scope } = await getTenant();
  const { response } = await api.POST("/support-requests", {
    params: scope,
    body: { message: String(formData.get("message") ?? "") },
  });
  if (!response.ok) return { error: response.status === 429 ? "too_many_requests" : "generic" };
  return { sent: true };
}
