"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

/** Saves the industry's extra fields (form inputs named `field.<key>`). */
export async function saveProfile(clientId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  const customFields: Record<string, string | null> = {};
  for (const [name, value] of formData.entries()) {
    if (name.startsWith("field.")) customFields[name.slice("field.".length)] = String(value) || null;
  }
  try {
    unwrap(
      await api.PATCH("/clients/{client_id}", {
        params: { ...scope, path: { client_id: clientId } },
        body: { custom_fields: customFields },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/clients/${clientId}`);
  return { saved: true };
}

export async function addNote(clientId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/clients/{client_id}/notes", {
        params: { ...scope, path: { client_id: clientId } },
        body: { body: String(formData.get("body") ?? ""), booking_id: String(formData.get("booking_id") ?? "") || null },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/clients/${clientId}`);
  return { saved: true };
}

export async function deleteNote(clientId: string, noteId: string): Promise<void> {
  const { api, scope } = await getTenant();
  const { response } = await api.DELETE("/clients/{client_id}/notes/{note_id}", {
    params: { ...scope, path: { client_id: clientId, note_id: noteId } },
  });
  if (!response.ok) throw new Error(`delete note failed: ${response.status}`);
  revalidatePath(`/clients/${clientId}`);
}
