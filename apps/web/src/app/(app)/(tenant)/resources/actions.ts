"use server";

import { redirect } from "next/navigation";

import { ApiError } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

export type ReserveState = { error?: "slot_taken" | "outside_hours" | "length_not_offered" | "invalid" | "generic" };

/** Reserves the chosen court and time for the chosen client, then opens the reservation. */
export async function reserve(serviceId: string, minutes: number, _state: ReserveState, formData: FormData): Promise<ReserveState> {
  const [roomId, startsAt] = String(formData.get("slot") ?? "").split("|");
  const clientId = String(formData.get("client_id") ?? "");
  if (!roomId || !startsAt || !clientId) return { error: "invalid" };
  const { api, scope } = await getTenantFor("bookings.manage");
  const { data, response, error } = await api.POST("/resources/reservations", {
    params: scope,
    body: { service_id: serviceId, room_id: roomId, starts_at: startsAt, minutes, client_id: clientId },
  });
  if (!data) {
    const detail = (new ApiError(response.status, error).body as { detail?: unknown } | null)?.detail;
    const known = ["slot_taken", "outside_hours", "length_not_offered"] as const;
    return { error: known.find((code) => code === detail) ?? (response.status === 422 ? "invalid" : "generic") };
  }
  redirect(`/schedule/${data.session_id}?booked=1`);
}
