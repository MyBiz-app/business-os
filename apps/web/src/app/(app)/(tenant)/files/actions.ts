"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { apiFetch, ApiError, unwrap } from "@/lib/api";
import type { FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

/** Adds a file to a folder. */
export async function uploadFile(folderId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { tenant } = await getTenant();
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) return { error: "invalid" };
  const body = new FormData();
  body.set("file", file);
  body.set("folder_id", folderId);
  body.set("name", String(formData.get("name") || file.name));
  const response = await apiFetch("/files", { method: "POST", body }, tenant.id);
  if (!response.ok) {
    // 409: the business's space for files is full (#104).
    return { error: response.status === 422 ? "invalid" : response.status === 409 ? "storage_full" : "generic" };
  }
  revalidatePath("/files");
  return { saved: true };
}

/** A folder of the business's own, inside the open folder. */
export async function createFolder(parentId: string | null, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  const name = String(formData.get("name") ?? "").trim();
  if (!name) return { error: "invalid" };
  try {
    unwrap(await api.POST("/files/folders", { params: scope, body: { name, parent_id: parentId } }));
  } catch (error) {
    return { error: error instanceof ApiError && (error.status === 422 || error.status === 409) ? "invalid" : "generic" };
  }
  revalidatePath("/files");
  return { saved: true };
}

export async function deleteFolder(folderId: string, parentId: string | null): Promise<void> {
  const { api, scope } = await getTenant();
  await api.DELETE("/files/folders/{folder_id}", { params: { ...scope, path: { folder_id: folderId } } });
  revalidatePath("/files");
  redirect(parentId ? `/files?folder=${parentId}` : "/files");
}

export async function setArchived(fileId: string, archived: boolean): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.PATCH("/files/{file_id}", { params: { ...scope, path: { file_id: fileId } }, body: { archived } }));
  revalidatePath("/files");
}

export async function deleteFile(fileId: string): Promise<void> {
  const { api, scope } = await getTenant();
  await api.DELETE("/files/{file_id}", { params: { ...scope, path: { file_id: fileId } } });
  revalidatePath("/files");
}
