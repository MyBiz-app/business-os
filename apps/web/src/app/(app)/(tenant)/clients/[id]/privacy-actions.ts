"use server";

import { revalidatePath } from "next/cache";

import { ApiError, unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

export type EraseState = { error?: "confirm" | "generic" };

/** Erases the client's personal data (privacy request). Records and payments are kept. */
export async function eraseClient(clientId: string, _state: EraseState, formData: FormData): Promise<EraseState> {
  if (formData.get("confirm") !== "on") return { error: "confirm" };
  const { api, scope } = await getTenantFor("clients.privacy");
  try {
    unwrap(
      await api.POST("/clients/{client_id}/erase", {
        params: { ...scope, path: { client_id: clientId } },
        body: { confirm: true },
      }),
    );
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 409)) return { error: "generic" };
  }
  revalidatePath(`/clients/${clientId}`);
  return {};
}
