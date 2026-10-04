"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

/** Approves or rejects a declaration that answered "yes" to a question. */
export async function reviewDeclaration(clientId: string, declarationId: string, formData: FormData): Promise<void> {
  const { api, scope } = await getTenantFor("clients.write");
  const note = String(formData.get("note") ?? "").trim();
  unwrap(
    await api.POST("/health-declarations/{declaration_id}/review", {
      params: { ...scope, path: { declaration_id: declarationId } },
      body: { approve: formData.get("decision") === "approve", note: note || null },
    }),
  );
  revalidatePath(`/clients/${clientId}`);
}
