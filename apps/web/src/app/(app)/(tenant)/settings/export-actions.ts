"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

/** The owner asks for a ZIP of the whole business; it is built in the background. */
export async function requestExport(): Promise<void> {
  const { api, scope } = await getTenant();
  await api.POST("/tenants/current/data-exports", { params: scope });
  revalidatePath("/settings");
}

/** Opens a ready export through a fresh 24-hour link (the browser downloads the ZIP). */
export async function downloadExport(formData: FormData): Promise<void> {
  const { api, scope } = await getTenant();
  const id = String(formData.get("id") ?? "");
  const link = unwrap(await api.POST("/tenants/current/data-exports/{export_id}/link", { params: { ...scope, path: { export_id: id } } }));
  redirect(link.url);
}
