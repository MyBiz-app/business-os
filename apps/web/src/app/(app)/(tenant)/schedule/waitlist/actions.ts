"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

export type EntryState = { error?: "spot_taken" | "no_free_spot" | "generic"; done?: boolean };

const detailOf = (error: unknown) => (error instanceof ApiError ? (error.body as { detail?: unknown } | null)?.detail : undefined);

function failed(error: unknown): EntryState {
  const detail = detailOf(error);
  if (detail === "spot_taken") return { error: "spot_taken" };
  if (detail === "no_free_spot" || detail === "spot_does_not_match") return { error: "no_free_spot" };
  return { error: "generic" };
}

/** Lets a waiting client in: a request takes the spot that opened for it, a place on a class's own list becomes a booking. */
export async function admitEntry(source: "request" | "booking", id: string, _state: EntryState): Promise<EntryState> {
  const { api, scope } = await getTenantFor("bookings.manage");
  try {
    const { response, error } =
      source === "request"
        ? await api.POST("/waitlist/requests/{request_id}/admit", { params: { ...scope, path: { request_id: id } }, body: {} })
        : await api.POST("/waitlist/bookings/{booking_id}/admit", { params: { ...scope, path: { booking_id: id } } });
    if (!response.ok) throw new ApiError(response.status, error);
  } catch (error) {
    return failed(error);
  }
  revalidatePath("/schedule", "layout");
  return { done: true };
}

/** Takes a request off the list, or cancels a place on a class's own list. */
export async function removeEntry(source: "request" | "booking", id: string, _state: EntryState): Promise<EntryState> {
  const { api, scope } = await getTenantFor("bookings.manage");
  try {
    const { response, error } =
      source === "request"
        ? await api.DELETE("/waitlist/requests/{request_id}", { params: { ...scope, path: { request_id: id } } })
        : await api.PATCH("/bookings/{booking_id}", { params: { ...scope, path: { booking_id: id } }, body: { status: "cancelled" } });
    if (!response.ok) throw new ApiError(response.status, error);
  } catch (error) {
    return failed(error);
  }
  revalidatePath("/schedule", "layout");
  return { done: true };
}

/** Tells a waiting client about the spot that is free for them now. */
export async function notifyEntry(id: string, _state: EntryState): Promise<EntryState> {
  const { api, scope } = await getTenantFor("bookings.manage");
  try {
    const { response, error } = await api.POST("/waitlist/requests/{request_id}/notify", { params: { ...scope, path: { request_id: id } } });
    if (!response.ok) throw new ApiError(response.status, error);
  } catch (error) {
    return failed(error);
  }
  revalidatePath("/schedule/waitlist");
  return { done: true };
}
