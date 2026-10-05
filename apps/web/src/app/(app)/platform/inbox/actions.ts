"use server";

import { revalidatePath } from "next/cache";

import { getPlatform } from "@/lib/platform";

export type InboxState = { error?: string; saved?: boolean };

type Update = { status?: "new" | "in_progress" | "done"; assignee?: string; notes?: string };

/** Moves a request along (status, who handles it, internal notes). */
export async function updateRequest(id: string, update: Update): Promise<InboxState> {
  const { api } = await getPlatform();
  const { response } = await api.PATCH("/platform/contact-requests/{request_id}", {
    params: { path: { request_id: id } },
    body: update,
  });
  if (!response.ok) return { error: "generic" };
  revalidatePath("/platform/inbox");
  revalidatePath("/platform");
  return { saved: true };
}

export async function saveNotes(id: string, _state: InboxState, formData: FormData): Promise<InboxState> {
  return updateRequest(id, { notes: String(formData.get("notes") ?? "") });
}
