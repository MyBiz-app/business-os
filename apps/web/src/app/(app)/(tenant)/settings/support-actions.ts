"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

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
