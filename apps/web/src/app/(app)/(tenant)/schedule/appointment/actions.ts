"use server";

import { redirect } from "next/navigation";

import { ApiError } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

export type AppointmentState = { error?: "slot_taken" | "outside_hours" | "invalid" | "generic" };

/** Books the chosen client into the chosen free time, then opens the appointment. */
export async function bookAppointment(serviceId: string, _state: AppointmentState, formData: FormData): Promise<AppointmentState> {
  const slot = String(formData.get("slot") ?? "");
  // "client" or "client|dependent" (who comes, in industries that keep pets / children).
  const [clientId, dependentId] = String(formData.get("client_id") ?? "").split("|");
  const [staffUserId, startsAt] = slot.split("|");
  if (!staffUserId || !startsAt || !clientId) return { error: "invalid" };
  const { api, scope } = await getTenantFor("bookings.manage");
  const { data, response, error } = await api.POST("/appointments", {
    params: scope,
    body: { service_id: serviceId, staff_user_id: staffUserId, starts_at: startsAt, client_id: clientId, dependent_id: dependentId || null },
  });
  if (!data) {
    const detail = (new ApiError(response.status, error).body as { detail?: unknown } | null)?.detail;
    return { error: detail === "slot_taken" || detail === "outside_hours" ? detail : response.status === 422 ? "invalid" : "generic" };
  }
  redirect(`/schedule/${data.session_id}?booked=1`);
}
