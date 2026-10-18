"use server";

import type { components } from "@business-os/api-client";
import { revalidatePath } from "next/cache";

import { apiFetch, ApiError, unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

type Brief = components["schemas"]["Brief"];

export type DraftResult = { ok: true; missing: string[] } | { ok: false; error: "locked" | "invalid" | "generic" };

function failure(error: unknown): DraftResult {
  if (error instanceof ApiError) {
    if (error.status === 409) return { ok: false, error: "locked" };
    if (error.status === 422) return { ok: false, error: "invalid" };
  }
  return { ok: false, error: "generic" };
}

/** Saves the answers so far (the brief is a draft after every step). */
export async function saveBrief(brief: Brief): Promise<DraftResult> {
  const { api, scope } = await getTenant();
  try {
    const state = unwrap(await api.PUT("/website/order", { params: scope, body: { brief } }));
    revalidatePath("/website");
    return { ok: true, missing: state.missing };
  } catch (error) {
    return failure(error);
  }
}

/** Sends the brief to MyBiz. */
export async function submitBrief(): Promise<DraftResult> {
  const { api, scope } = await getTenant();
  try {
    unwrap(await api.POST("/website/order/submit", { params: scope }));
    revalidatePath("/website");
    return { ok: true, missing: [] };
  } catch (error) {
    return failure(error);
  }
}

export type UploadResult = { ok: true; fileId: string; name: string } | { ok: false; error: "invalid" | "storage_full" | "generic" };

/** Adds a logo or a photo to the business's "Website" folder in the files area. */
export async function uploadSiteImage(folderId: string, formData: FormData): Promise<UploadResult> {
  const { tenant } = await getTenant();
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) return { ok: false, error: "invalid" };
  const body = new FormData();
  body.set("file", file);
  body.set("folder_id", folderId);
  const response = await apiFetch("/files", { method: "POST", body }, tenant.id);
  if (!response.ok) return { ok: false, error: response.status === 422 ? "invalid" : response.status === 409 ? "storage_full" : "generic" };
  const saved = (await response.json()) as { id: string; name: string };
  return { ok: true, fileId: saved.id, name: saved.name };
}

/** The business's answer to a site waiting for its review: approve, or ask for changes. */
export async function respondToSite(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  const action = formData.get("action") === "approve" ? "approve" : "changes";
  try {
    unwrap(await api.POST("/website/order/respond", { params: scope, body: { action, message: String(formData.get("message") ?? "") } }));
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/website");
  return { saved: true };
}

/** A website-only business adds the system: its modules open and it keeps its account. */
export async function addSystem(_state: FormState): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(await api.POST("/website/add-system", { params: scope }));
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/", "layout");
  return { saved: true };
}
