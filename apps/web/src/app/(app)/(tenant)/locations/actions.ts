"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { apiUpload, unwrap } from "@/lib/api";
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
          ...(formData.has("kind") ? { kind: value(formData, "kind") || null } : {}),
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

/** A branch's opening hours (one or more intervals per day; a gap is a break). */
export async function saveOpeningHours(locationId: string, blocks: Block[]): Promise<HoursState> {
  if (blocks.some((block) => !block.starts || !block.ends || block.ends <= block.starts)) {
    return { error: "invalid" };
  }
  const { api, scope } = await getTenantFor("catalog.write");
  const { response } = await api.PUT("/locations/{location_id}/hours", {
    params: { ...scope, path: { location_id: locationId } },
    body: { intervals: blocks.map((b) => ({ weekday: b.weekday, opens: b.starts, closes: b.ends })) },
  });
  if (!response.ok) return { error: response.status === 422 ? "overlapping_hours" : "generic" };
  revalidatePath(`/locations/${locationId}`);
  revalidatePath("/schedule");
  return { saved: true };
}

/** Adds a branch to a running business; the owner must have accepted the extra monthly charge. */
export async function addBranch(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenantFor("business.settings");
  const copyFrom = value(formData, "copy_hours_from");
  let id: string;
  try {
    id = unwrap(
      await api.POST("/locations/new-branch", {
        params: scope,
        body: {
          name: value(formData, "name"),
          address: value(formData, "address"),
          kind: value(formData, "kind") || null,
          copy_hours_from: copyFrom === "" ? null : copyFrom,
          staff_user_ids: formData.getAll("staff_user_ids").map(String),
          accept_extra_charge: formData.get("accept_extra_charge") === "on",
        },
      }),
    ).id;
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/locations");
  revalidatePath("/team");
  redirect(`/locations/${id}`);
}

export type BrandingState = { error?: "logo_too_large" | "unsupported_image" | "generic"; saved?: boolean };

/** A branch's own logo (the business's logo shows until one is set). */
export async function uploadBranchLogo(locationId: string, _state: BrandingState, formData: FormData): Promise<BrandingState> {
  const file = formData.get("logo");
  if (!(file instanceof File) || file.size === 0) return { error: "unsupported_image" };
  const { tenant } = await getTenant();
  const response = await apiUpload(`/locations/${locationId}/logo`, file, tenant.id);
  if (response.status === 413) return { error: "logo_too_large" };
  if (response.status === 415) return { error: "unsupported_image" };
  if (!response.ok) return { error: "generic" };
  revalidatePath("/", "layout");
  return { saved: true };
}

export async function removeBranchLogo(locationId: string): Promise<void> {
  const { api, scope } = await getTenant();
  await api.DELETE("/locations/{location_id}/logo", { params: { ...scope, path: { location_id: locationId } } });
  revalidatePath("/", "layout");
}

export async function updateBranchColor(locationId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  const color = formData.get("use_network") === "on" ? null : String(formData.get("primary_color"));
  try {
    unwrap(
      await api.PATCH("/locations/{location_id}", {
        params: { ...scope, path: { location_id: locationId } },
        body: { primary_color: color },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/", "layout");
  return { saved: true };
}

/** Whether clients and friends are shared by the whole network or kept per branch. */
export async function updateNetworkScope(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenantFor("business.settings");
  try {
    unwrap(
      await api.PATCH("/tenants/current", {
        params: scope,
        body: { network_scope: value(formData, "network_scope") === "branch" ? "branch" : "network" },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/", "layout");
  return { saved: true };
}

/** Creates (`groupId` null) or updates a branch group: its name and the branches in it. */
export async function saveLocationGroup(
  groupId: string | null,
  _state: FormState,
  formData: FormData,
): Promise<FormState> {
  const { api, scope } = await getTenant();
  const body = {
    name: value(formData, "name"),
    location_ids: formData.getAll("location_id").map(String),
  };
  try {
    if (groupId === null) {
      unwrap(await api.POST("/location-groups", { params: scope, body }));
    } else {
      unwrap(
        await api.PATCH("/location-groups/{group_id}", {
          params: { ...scope, path: { group_id: groupId } },
          body,
        }),
      );
    }
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/locations");
  return { saved: true };
}

export async function deleteLocationGroup(groupId: string): Promise<void> {
  const { api, scope } = await getTenant();
  await api.DELETE("/location-groups/{group_id}", { params: { ...scope, path: { group_id: groupId } } });
  revalidatePath("/locations");
}

/** Appoints a team member as the branch's manager, or (empty) leaves it to the owner. */
export async function setBranchManager(locationId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenantFor("business.settings");
  const userId = String(formData.get("user_id") ?? "");
  try {
    if (userId) {
      unwrap(
        await api.PUT("/locations/{location_id}/manager", {
          params: { ...scope, path: { location_id: locationId } },
          body: { user_id: userId },
        }),
      );
    } else {
      unwrap(await api.DELETE("/locations/{location_id}/manager", { params: { ...scope, path: { location_id: locationId } } }));
    }
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/", "layout");
  return { saved: true };
}
