"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

function read(formData: FormData) {
  const value = (name: string) => String(formData.get(name) ?? "").trim() || null;
  return {
    label: value("label"),
    street: value("street") ?? "",
    city: value("city") ?? "",
    details: value("details"),
    notes: value("notes"),
  };
}

export async function addAddress(clientId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/clients/{client_id}/addresses", {
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

export async function saveAddress(
  clientId: string,
  addressId: string,
  _state: FormState,
  formData: FormData,
): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.PATCH("/addresses/{address_id}", {
        params: { ...scope, path: { address_id: addressId } },
        body: read(formData),
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/clients/${clientId}`);
  return { saved: true };
}

export async function setAddressActive(clientId: string, addressId: string, active: boolean): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(
    await api.PATCH("/addresses/{address_id}", {
      params: { ...scope, path: { address_id: addressId } },
      body: { active },
    }),
  );
  revalidatePath(`/clients/${clientId}`);
}
