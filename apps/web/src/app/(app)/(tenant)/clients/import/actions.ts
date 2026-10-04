"use server";

import type { components } from "@business-os/api-client";
import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

export type ImportResult = components["schemas"]["ImportResult"];
export type ImportField = NonNullable<ImportResult["mapping"][number]>;

export type ImportState = {
  result?: ImportResult;
  error?: "file_too_large" | "empty_file" | "too_many_rows" | "unreadable_file" | "email_taken" | "generic";
};

const KNOWN = ["file_too_large", "empty_file", "too_many_rows", "unreadable_file", "email_taken"] as const;

/** Sends the file to the API: a preview (commit=false) or the import itself. */
export async function runImport(formData: FormData): Promise<ImportState> {
  const { tenant } = await getTenantFor("clients.write");
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) return { error: "empty_file" };
  const body = new FormData();
  body.set("file", file);
  for (const key of ["mapping", "commit", "source"]) {
    const value = formData.get(key);
    if (typeof value === "string" && value) body.set(key, value);
  }
  const response = await apiFetch("/clients/import", { method: "POST", body }, tenant.id);
  if (!response.ok) {
    const detail = ((await response.json().catch(() => null)) as { detail?: unknown } | null)?.detail;
    return { error: KNOWN.find((code) => code === detail) ?? "generic" };
  }
  const result = (await response.json()) as ImportResult;
  if (result.imported) revalidatePath("/clients");
  return { result };
}
