"use server";

import { redirect } from "next/navigation";

import { getApi, unwrap } from "@/lib/api";
import { setActiveTenant } from "@/lib/tenant";

export async function acceptInvitation(token: string): Promise<void> {
  const api = await getApi();
  const { tenant_id } = unwrap(await api.POST("/invitations/accept", { body: { token } }));
  await setActiveTenant(tenant_id);
  redirect("/dashboard");
}
