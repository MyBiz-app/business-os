"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";


/** Approves or rejects a change an AI app suggested. The API checks everything again at this
 * moment; when it refuses (a full class, an expired request) the list shows the outcome. */
export async function decideRequest(id: string, decision: "confirm" | "reject"): Promise<void> {
  const { api, scope } = await getTenant();
  try {
    await api.POST(decision === "confirm" ? "/ai/pending-actions/{action_id}/confirm" : "/ai/pending-actions/{action_id}/reject", {
      params: { ...scope, path: { action_id: id } },
    });
  } finally {
    revalidatePath("/settings", "layout");
  }
}

export async function disconnectApp(id: string): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.DELETE("/mcp-connections/{connection_id}", { params: { ...scope, path: { connection_id: id } } }));
  revalidatePath("/settings", "layout");
}
