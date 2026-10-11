"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

/** The form's values: name, birth date, notes and the pack's fields (`field.<key>`). */
function read(formData: FormData) {
  const details: Record<string, string | null> = {};
  for (const [name, value] of formData.entries()) {
    if (name.startsWith("field.")) details[name.slice("field.".length)] = String(value) || null;
  }
  return {
    name: String(formData.get("name") ?? ""),
    birth_date: String(formData.get("birth_date") ?? "") || null,
    notes: String(formData.get("notes") ?? "") || null,
    details,
  };
}

export async function addDependent(clientId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/clients/{client_id}/dependents", {
        params: { ...scope, path: { client_id: clientId } },
        body: read(formData),
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/clients/${clientId}`);
  return { saved: true };
}

export async function saveDependent(
  clientId: string,
  dependentId: string,
  _state: FormState,
  formData: FormData,
): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.PATCH("/dependents/{dependent_id}", {
        params: { ...scope, path: { dependent_id: dependentId } },
        body: read(formData),
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/clients/${clientId}`);
  return { saved: true };
}

export async function setDependentActive(clientId: string, dependentId: string, active: boolean): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(
    await api.PATCH("/dependents/{dependent_id}", {
      params: { ...scope, path: { dependent_id: dependentId } },
      body: { active },
    }),
  );
  revalidatePath(`/clients/${clientId}`);
}
