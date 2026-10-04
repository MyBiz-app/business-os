"use server";

import { revalidatePath } from "next/cache";

import { ApiError, unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

export type CloseDayState = { error?: "already_closed" | "invalid" | "generic"; cancelled?: number };

export async function closeDay(_state: CloseDayState, formData: FormData): Promise<CloseDayState> {
  const { api, scope } = await getTenantFor("schedule.write");
  const reason = String(formData.get("reason") ?? "").trim();
  try {
    const result = unwrap(
      await api.POST("/closed-days", {
        params: scope,
        body: { day: String(formData.get("day") ?? ""), reason: reason || null },
      }),
    );
    revalidatePath("/schedule", "layout");
    return { cancelled: result.cancelled_sessions };
  } catch (error) {
    if (error instanceof ApiError) {
      if ((error.body as { detail?: unknown } | null)?.detail === "already_closed") return { error: "already_closed" };
      if (error.status === 422) return { error: "invalid" };
    }
    return { error: "generic" };
  }
}

export async function reopenDay(closedDayId: string): Promise<void> {
  const { api, scope } = await getTenantFor("schedule.write");
  const { response, error } = await api.DELETE("/closed-days/{closed_day_id}", {
    params: { ...scope, path: { closed_day_id: closedDayId } },
  });
  if (!response.ok) throw new ApiError(response.status, error);
  revalidatePath("/schedule", "layout");
}
