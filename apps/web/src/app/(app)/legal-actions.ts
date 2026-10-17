"use server";

import { revalidatePath } from "next/cache";

import { getApi } from "@/lib/api";

/** Accepts the current version of the documents named in the banner. The API refuses a version
 * that is no longer the current one, so a stale page cannot record the wrong text. */
export async function acceptLegal(formData: FormData): Promise<void> {
  let documents: Record<string, string>;
  try {
    documents = JSON.parse(String(formData.get("documents") ?? "{}")) as Record<string, string>;
  } catch {
    return;
  }
  if (Object.keys(documents).length === 0) return;
  await (await getApi()).POST("/me/legal", { body: { documents } });
  revalidatePath("/", "layout");
}
