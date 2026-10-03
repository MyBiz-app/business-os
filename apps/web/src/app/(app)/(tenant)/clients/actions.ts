"use server";

import type { components } from "@business-os/api-client";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiError, unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

export type ClientFormState = { error?: "email_taken" | "invalid" | "generic"; saved?: boolean };

type ClientStatus = components["schemas"]["ClientCreate"]["status"];

function readForm(formData: FormData) {
  const value = (name: string) => String(formData.get(name) ?? "");
  return {
    first_name: value("first_name"),
    last_name: value("last_name"),
    email: value("email"),
    phone: value("phone"),
    date_of_birth: value("date_of_birth") || null,
    notes: value("notes"),
    status: (value("status") || "active") as ClientStatus,
  };
}

function toState(error: unknown): ClientFormState {
  if (error instanceof ApiError) {
    if (error.status === 409) return { error: "email_taken" };
    if (error.status === 422) return { error: "invalid" };
  }
  return { error: "generic" };
}

export async function createClient(
  _state: ClientFormState,
  formData: FormData,
): Promise<ClientFormState> {
  const { api, scope } = await getTenant();
  let id: string;
  try {
    id = unwrap(await api.POST("/clients", { params: scope, body: readForm(formData) })).id;
  } catch (error) {
    return toState(error);
  }
  revalidatePath("/clients");
  redirect(`/clients/${id}`);
}

export async function updateClient(
  clientId: string,
  _state: ClientFormState,
  formData: FormData,
): Promise<ClientFormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.PATCH("/clients/{client_id}", {
        params: { ...scope, path: { client_id: clientId } },
        body: readForm(formData),
      }),
    );
  } catch (error) {
    return toState(error);
  }
  revalidatePath("/clients");
  revalidatePath(`/clients/${clientId}`);
  return { saved: true };
}
