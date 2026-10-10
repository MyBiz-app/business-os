"use server";

import { revalidatePath } from "next/cache";

import type { Palette } from "@/components/palette";
import { apiFetch, apiUpload, getApi, unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";

export async function saveProfile(_state: FormState, formData: FormData): Promise<FormState> {
  try {
    unwrap(
      await (await getApi()).PATCH("/me", {
        body: { full_name: String(formData.get("full_name") ?? ""), phone: String(formData.get("phone") ?? "") },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/", "layout");
  return { saved: true };
}

export type PictureState = { error?: "image_too_large" | "unsupported_image" | "generic"; saved?: boolean };

export async function uploadAvatar(_state: PictureState, formData: FormData): Promise<PictureState> {
  const file = formData.get("avatar");
  if (!(file instanceof File) || file.size === 0) return { error: "unsupported_image" };
  // The picture is the person's own; no business is involved.
  const response = await apiUpload("/me/avatar", file, "");
  if (response.status === 413) return { error: "image_too_large" };
  if (response.status === 415) return { error: "unsupported_image" };
  if (!response.ok) return { error: "generic" };
  revalidatePath("/", "layout");
  return { saved: true };
}

export async function removeAvatar(): Promise<void> {
  await apiFetch("/me/avatar", { method: "DELETE" }, "");
  revalidatePath("/", "layout");
}

export async function savePalette(palette: Palette): Promise<void> {
  await (await getApi()).PATCH("/me", { body: { palette } });
}
