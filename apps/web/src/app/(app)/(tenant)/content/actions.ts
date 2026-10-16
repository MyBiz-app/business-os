"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiError, unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

/** Connects the sample accounts, so the dashboard can be seen before any real network is. */
export async function connectDemo(): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.POST("/social/connect/{provider}", { params: { ...scope, path: { provider: "demo" } } }));
  revalidatePath("/content");
}

export async function disconnectAccount(id: string): Promise<void> {
  const { api, scope } = await getTenant();
  const result = await api.DELETE("/social/accounts/{account_id}", { params: { ...scope, path: { account_id: id } } });
  if (!result.response.ok && result.response.status !== 404) throw new ApiError(result.response.status, result.error);
  revalidatePath("/content");
}

/** "Refresh now": the API allows it once an hour; asking sooner just keeps the current numbers. */
export async function refreshNow(): Promise<void> {
  const { api, scope } = await getTenant();
  const result = await api.POST("/social/sync", { params: scope });
  if (!result.response.ok && result.response.status !== 429) throw new ApiError(result.response.status, result.error);
  revalidatePath("/content");
}

/** "Connect" on a network whose connector is ready: the owner agrees on the network's own page. */
export async function startConnect(provider: string): Promise<void> {
  const { api, scope } = await getTenant();
  const result = unwrap(await api.POST("/social/connect/{provider}", { params: { ...scope, path: { provider } } }));
  if (result.authorize_url) redirect(result.authorize_url);
  revalidatePath("/content");
}
