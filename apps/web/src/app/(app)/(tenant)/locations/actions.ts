"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

const value = (formData: FormData, name: string) => String(formData.get(name) ?? "");
const optionalNumber = (formData: FormData, name: string) => {
  const raw = value(formData, name).trim();
  return raw === "" ? null : Number(raw);
};

export async function createLocation(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  let id: string;
  try {
    id = unwrap(
      await api.POST("/locations", {
        params: scope,
        body: { name: value(formData, "name"), address: value(formData, "address") },
      }),
    ).id;
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/locations");
  redirect(`/locations/${id}`);
}

export async function updateLocation(
  locationId: string,
  _state: FormState,
  formData: FormData,
): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.PATCH("/locations/{location_id}", {
        params: { ...scope, path: { location_id: locationId } },
        body: {
          name: value(formData, "name"),
          address: value(formData, "address"),
          active: formData.get("active") === "on",
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/locations");
  revalidatePath(`/locations/${locationId}`);
  return { saved: true };
}

export async function addRoom(
  locationId: string,
  _state: FormState,
  formData: FormData,
): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/locations/{location_id}/rooms", {
        params: { ...scope, path: { location_id: locationId } },
        body: { name: value(formData, "name"), capacity: optionalNumber(formData, "capacity") },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/locations/${locationId}`);
  return {};
}

export async function updateRoom(
  roomId: string,
  locationId: string,
  _state: FormState,
  formData: FormData,
): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.PATCH("/rooms/{room_id}", {
        params: { ...scope, path: { room_id: roomId } },
        body: {
          name: value(formData, "name"),
          capacity: optionalNumber(formData, "capacity"),
          active: formData.get("active") === "on",
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/locations/${locationId}`);
  return { saved: true };
}
