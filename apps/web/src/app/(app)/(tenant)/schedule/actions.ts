"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiError, unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

export type SessionFormState = {
  error?: "invalid_reference" | "no_occurrences" | "invalid" | "generic";
  saved?: boolean;
};

function toState(error: unknown): SessionFormState {
  if (error instanceof ApiError) {
    const detail = (error.body as { detail?: unknown } | null)?.detail;
    if (detail === "invalid_reference" || detail === "no_occurrences") return { error: detail };
    if (error.status === 422) return { error: "invalid" };
  }
  return { error: "generic" };
}

const text = (formData: FormData, name: string) => String(formData.get(name) ?? "").trim();
const optional = (formData: FormData, name: string) => text(formData, name) || null;
const optionalNumber = (formData: FormData, name: string) => {
  const value = text(formData, name);
  return value ? Number(value) : null;
};

/** "<location_id>:<room_id>" or "<location_id>:" from the combined place select. */
function readPlace(formData: FormData) {
  const [location, room] = text(formData, "place").split(":");
  return { location_id: location || null, room_id: room || null };
}

export async function createSessions(_state: SessionFormState, formData: FormData): Promise<SessionFormState> {
  const { api, scope } = await getTenant();
  const date = text(formData, "date");
  const weekdays = formData.getAll("weekdays").map(Number);
  try {
    unwrap(
      await api.POST("/sessions", {
        params: scope,
        body: {
          service_id: text(formData, "service_id"),
          date,
          start_time: text(formData, "start_time"),
          duration_minutes: optionalNumber(formData, "duration_minutes"),
          capacity: optionalNumber(formData, "capacity"),
          instructor_user_id: optional(formData, "instructor_user_id"),
          notes: optional(formData, "notes"),
          ...readPlace(formData),
          repeat:
            formData.get("repeat") === "on"
              ? { weekdays, ends_on: optional(formData, "ends_on") }
              : null,
        },
      }),
    );
  } catch (error) {
    return toState(error);
  }
  revalidatePath("/schedule");
  redirect(`/schedule?week=${date}`);
}

export async function updateSession(
  sessionId: string,
  _state: SessionFormState,
  formData: FormData,
): Promise<SessionFormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.PATCH("/sessions/{session_id}", {
        params: { ...scope, path: { session_id: sessionId } },
        body: {
          date: text(formData, "date"),
          start_time: text(formData, "start_time"),
          duration_minutes: optionalNumber(formData, "duration_minutes"),
          capacity: optionalNumber(formData, "capacity"),
          instructor_user_id: optional(formData, "instructor_user_id"),
          notes: optional(formData, "notes"),
          ...readPlace(formData),
        },
      }),
    );
  } catch (error) {
    return toState(error);
  }
  revalidatePath("/schedule");
  revalidatePath(`/schedule/${sessionId}`);
  return { saved: true };
}

export async function setSessionStatus(sessionId: string, status: "scheduled" | "cancelled"): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(
    await api.PATCH("/sessions/{session_id}", {
      params: { ...scope, path: { session_id: sessionId } },
      body: { status },
    }),
  );
  revalidatePath("/schedule");
  revalidatePath(`/schedule/${sessionId}`);
}

function bookingError(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = (error.body as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string") return detail;
  }
  return "generic";
}

function refreshSession(sessionId: string) {
  revalidatePath("/schedule");
  revalidatePath(`/schedule/${sessionId}`);
}

export async function bookClient(sessionId: string, clientId: string): Promise<void> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/sessions/{session_id}/bookings", {
        params: { ...scope, path: { session_id: sessionId } },
        body: { client_id: clientId },
      }),
    );
  } catch (error) {
    redirect(`/schedule/${sessionId}?error=${bookingError(error)}`);
  }
  refreshSession(sessionId);
  redirect(`/schedule/${sessionId}`);
}

export async function setBookingStatus(
  sessionId: string,
  bookingId: string,
  status: "booked" | "checked_in" | "no_show" | "cancelled",
): Promise<void> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.PATCH("/bookings/{booking_id}", {
        params: { ...scope, path: { booking_id: bookingId } },
        body: { status },
      }),
    );
  } catch (error) {
    redirect(`/schedule/${sessionId}?error=${bookingError(error)}`);
  }
  refreshSession(sessionId);
}

export async function endSeries(seriesId: string, sessionId: string, lastDate: string): Promise<void> {
  const { api, scope } = await getTenant();
  const result = unwrap(
    await api.POST("/series/{series_id}/end", {
      params: { ...scope, path: { series_id: seriesId } },
      body: { last_date: lastDate },
    }),
  );
  revalidatePath("/schedule");
  redirect(`/schedule/${sessionId}?ended=${result.cancelled}-${result.kept}`);
}
