"use server";

import { localToInstant } from "@business-os/i18n/dates";
import { revalidatePath } from "next/cache";

import { ApiError, unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

/** The outcome of a time clock form: an API error code (translated by the form) or "saved". */
export type ClockFormState = { error?: string; saved?: boolean };

const fail = (error: unknown): ClockFormState => {
  const detail = error instanceof ApiError && typeof (error.body as { detail?: unknown })?.detail === "string" ? ((error.body as { detail: string }).detail) : "generic";
  return { error: detail };
};

/** For answers without a body (204): throws the API's error when there is one. */
function expectOk(result: { error?: unknown; response: Response }) {
  if (result.error !== undefined || !result.response.ok) throw new ApiError(result.response.status, result.error);
}

const text = (formData: FormData, name: string) => String(formData.get(name) ?? "").trim();
const done = (userId: string): ClockFormState => {
  revalidatePath("/team/time-clock");
  revalidatePath(`/team/time-clock/${userId}`);
  return { saved: true };
};

/** Fixes the times of an entry; the reason is required and is kept in the log. */
export async function correctEntry(entryId: string, userId: string, _state: ClockFormState, formData: FormData): Promise<ClockFormState> {
  const { api, scope, tenant } = await getTenantFor("time.approve");
  const clockIn = text(formData, "clock_in");
  const clockOut = text(formData, "clock_out");
  try {
    unwrap(
      await api.PATCH("/time-clock/entries/{entry_id}", {
        params: { ...scope, path: { entry_id: entryId } },
        body: {
          clock_in: clockIn ? localToInstant(clockIn, tenant.time_zone) : null,
          clock_out: clockOut ? localToInstant(clockOut, tenant.time_zone) : null,
          reason: text(formData, "reason"),
        },
      }),
    );
  } catch (error) {
    return fail(error);
  }
  return done(userId);
}

/** Records time that was never clocked. */
export async function addEntry(userId: string, _state: ClockFormState, formData: FormData): Promise<ClockFormState> {
  const { api, scope, tenant } = await getTenantFor("time.approve");
  const clockIn = text(formData, "clock_in");
  const clockOut = text(formData, "clock_out");
  if (!clockIn || !clockOut) return { error: "invalid_period" };
  try {
    unwrap(
      await api.POST("/time-clock/entries", {
        params: scope,
        body: {
          user_id: userId,
          location_id: text(formData, "location_id"),
          clock_in: localToInstant(clockIn, tenant.time_zone),
          clock_out: localToInstant(clockOut, tenant.time_zone),
          reason: text(formData, "reason"),
        },
      }),
    );
  } catch (error) {
    return fail(error);
  }
  return done(userId);
}

export async function deleteEntry(entryId: string, userId: string, _state: ClockFormState, formData: FormData): Promise<ClockFormState> {
  const { api, scope } = await getTenantFor("time.approve");
  try {
    expectOk(
      await api.DELETE("/time-clock/entries/{entry_id}", {
        params: { ...scope, path: { entry_id: entryId }, query: { reason: text(formData, "reason") } },
      }),
    );
  } catch (error) {
    return fail(error);
  }
  return done(userId);
}

/** Approves (locks) or reopens a person's month. */
export async function setApproval(userId: string, month: string, approve: boolean, _state: ClockFormState): Promise<ClockFormState> {
  const { api, scope } = await getTenantFor("time.approve");
  const params = { ...scope, path: { user_id: userId }, query: { month } };
  try {
    if (approve) expectOk(await api.PUT("/time-clock/people/{user_id}/approval", { params }));
    else expectOk(await api.DELETE("/time-clock/people/{user_id}/approval", { params }));
  } catch (error) {
    return fail(error);
  }
  return done(userId);
}

export async function saveRules(_state: ClockFormState, formData: FormData): Promise<ClockFormState> {
  const { api, scope } = await getTenantFor("business.settings");
  const number = (name: string) => Number(text(formData, name));
  try {
    unwrap(
      await api.PUT("/time-clock/rules", {
        params: scope,
        body: {
          work_days_per_week: number("work_days_per_week") === 6 ? 6 : 5,
          week_hours: number("week_hours"),
          day_hours_5: number("day_hours_5"),
          day_hours_6: number("day_hours_6"),
          tier1_hours: number("tier1_hours"),
          tier1_percent: number("tier1_percent"),
          tier2_percent: number("tier2_percent"),
          rest_day_percent: number("rest_day_percent"),
          rest_weekday: number("rest_weekday"),
        },
      }),
    );
  } catch (error) {
    return fail(error);
  }
  revalidatePath("/team/time-clock");
  return { saved: true };
}
