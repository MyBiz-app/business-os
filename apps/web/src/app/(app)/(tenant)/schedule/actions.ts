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
