"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import type { Block, HoursState } from "@/lib/hours";
import { getTenant, getTenantFor } from "@/lib/tenant";

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
        body: {
          name: value(formData, "name"),
          capacity: optionalNumber(formData, "capacity"),
          bookable: formData.get("bookable") === "on",
        },
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
          bookable: formData.get("bookable") === "on",
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/locations/${locationId}`);
  return { saved: true };
}

/** A bookable room's weekly opening hours (when it can be reserved). */
export async function saveRoomHours(roomId: string, locationId: string, blocks: Block[]): Promise<HoursState> {
  if (blocks.some((block) => !block.starts || !block.ends || block.ends <= block.starts)) {
    return { error: "invalid" };
  }
  const { api, scope } = await getTenantFor("catalog.write");
  const { response, error } = await api.PUT("/rooms/{room_id}/hours", {
    params: { ...scope, path: { room_id: roomId } },
    body: blocks,
  });
  if (!response.ok) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    return { error: detail === "overlapping_hours" ? "overlapping_hours" : response.status === 422 ? "invalid" : "generic" };
  }
  revalidatePath(`/locations/${locationId}/rooms/${roomId}`);
  return { saved: true };
}
