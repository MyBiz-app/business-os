"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiError, unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

export type SessionFormState = {
  error?: "invalid_reference" | "no_occurrences" | "invalid" | "generic";
  saved?: boolean;
  /** Where a window over the schedule goes once the form is saved. */
  next?: string;
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
  // In a window over the schedule the form closes itself, shows the confirmation and opens the week.
  if (formData.get("_modal")) return { saved: true, next: `/schedule?week=${date}` };
  redirect(`/schedule?week=${date}`);
}

export async function updateSession(
  sessionId: string,
  series: { id: string; date: string } | null,
  _state: SessionFormState,
  formData: FormData,
): Promise<SessionFormState> {
  const { api, scope } = await getTenant();
  try {
    if (series && formData.get("apply_to_series") === "on") {
      // This and all following sessions of the series (the date field is not used).
      unwrap(
        await api.PATCH("/series/{series_id}", {
          params: { ...scope, path: { series_id: series.id } },
          body: {
            from_date: series.date,
            start_time: text(formData, "start_time"),
            duration_minutes: Number(text(formData, "duration_minutes")),
            capacity: Number(text(formData, "capacity")),
            instructor_user_id: optional(formData, "instructor_user_id"),
            notes: optional(formData, "notes"),
            ...readPlace(formData),
          },
        }),
      );
      revalidatePath("/schedule", "layout");
      return { saved: true };
    }
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

export async function bookClient(sessionId: string, clientId: string, dependentId: string | undefined): Promise<void> {
  await placeBooking(sessionId, clientId, dependentId, false);
}

/** "Add me" in a class roster: the signed-in team member becomes a client (if not yet) and is booked. */
export async function bookMyself(sessionId: string): Promise<void> {
  const { api, scope } = await getTenant();
  let clientId: string;
  try {
    clientId = unwrap(await api.POST("/clients/me", { params: scope })).id;
  } catch (error) {
    redirect(`/schedule/${sessionId}?error=${bookingError(error)}`);
  }
  await placeBooking(sessionId, clientId, undefined, false);
}

/** Adds a client to a full class beyond its capacity (owners and managers; the API checks). */
export async function bookClientOverCapacity(sessionId: string, clientId: string): Promise<void> {
  await placeBooking(sessionId, clientId, undefined, true);
}

async function placeBooking(
  sessionId: string,
  clientId: string,
  dependentId: string | undefined,
  overCapacity: boolean,
): Promise<void> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/sessions/{session_id}/bookings", {
        params: { ...scope, path: { session_id: sessionId } },
        body: { client_id: clientId, dependent_id: dependentId ?? null, over_capacity: overCapacity },
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

/** Gives the visit back to a client whose late cancellation or no-show used it up (an exception;
 * the reason is required and kept with who and when). */
export async function waiveBooking(sessionId: string, bookingId: string, formData: FormData): Promise<void> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/bookings/{booking_id}/waive", {
        params: { ...scope, path: { booking_id: bookingId } },
        body: { reason: String(formData.get("reason") ?? "").trim() },
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

export type CopyWeekState = { error?: "generic"; copied?: { created: number; skipped: number } };

/** Copies the week's one-off sessions to the next week. */
export async function copyWeek(weekStart: string, _state: CopyWeekState, _formData: FormData): Promise<CopyWeekState> {
  const { api, scope } = await getTenant();
  const next = new Date(`${weekStart}T12:00:00Z`);
  next.setUTCDate(next.getUTCDate() + 7);
  try {
    const copied = unwrap(
      await api.POST("/sessions/copy-week", {
        params: scope,
        body: { from_date: weekStart, to_date: next.toISOString().slice(0, 10) },
      }),
    );
    revalidatePath("/schedule");
    return { copied };
  } catch {
    return { error: "generic" };
  }
}

export type PublishWeekState = { error?: "generic"; published?: string; already?: boolean };

/** Opens the next week of classes for clients ahead of the scheduled release. */
export async function publishWeek(_state: PublishWeekState, _formData: FormData): Promise<PublishWeekState> {
  const { api, scope } = await getTenant();
  try {
    const { published_until } = unwrap(await api.POST("/sessions/publish-week", { params: scope }));
    revalidatePath("/schedule");
    return { published: published_until };
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) return { already: true };
    return { error: "generic" };
  }
}

/** Records that a reservation was paid at the venue (cash, card at the desk…); issues a receipt. */
export async function recordVenuePayment(sessionId: string, bookingId: string, formData: FormData): Promise<void> {
  const { api, scope } = await getTenant();
  const method = String(formData.get("method") ?? "cash");
  unwrap(
    await api.POST("/resources/reservations/{booking_id}/payment", {
      params: { ...scope, path: { booking_id: bookingId } },
      body: { method: (["card", "cash", "transfer", "other"].includes(method) ? method : "cash") as "card" | "cash" | "transfer" | "other" },
    }),
  );
  revalidatePath(`/schedule/${sessionId}`);
}

/** Moves an on-site job one step (#42): on the way, in progress, done. */
export async function setJobStatus(
  sessionId: string,
  status: "scheduled" | "on_the_way" | "in_progress" | "done",
): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(
    await api.POST("/jobs/{session_id}/status", {
      params: { ...scope, path: { session_id: sessionId } },
      body: { status },
    }),
  );
  refreshSession(sessionId);
}

export type DefaultViewState = { saved?: boolean; error?: boolean };

/** The owner's choice of how the schedule opens: the range and the branches side by side. */
export async function saveScheduleDefault(
  view: "day" | "week" | "month",
  branches: string[],
  _state: DefaultViewState,
  _formData: FormData,
): Promise<DefaultViewState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(await api.PATCH("/tenants/current", { params: scope, body: { schedule_default_view: view, schedule_default_branches: branches } }));
  } catch {
    return { error: true };
  }
  revalidatePath("/", "layout");
  return { saved: true };
}
