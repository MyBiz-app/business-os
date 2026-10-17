"use server";

import { revalidatePath } from "next/cache";

import { getPlatform } from "@/lib/platform";

/** Gives a business more time to pay: lifts read-only or suspension now (the API checks the right). */
export async function extendGrace(tenantId: string, formData: FormData): Promise<void> {
  const { api } = await getPlatform();
  const days = Math.min(90, Math.max(1, Number(formData.get("days")) || 7));
  await api.POST("/platform/businesses/{tenant_id}/billing/grace", {
    params: { path: { tenant_id: tenantId } },
    body: { days },
  });
  revalidatePath("/platform/billing");
}

export type DunningState = { error?: "invalid" | "generic"; saved?: boolean };

/** Saves the collection steps: the reminder days, and when a business turns read-only or is suspended. */
export async function saveDunning(_state: DunningState, formData: FormData): Promise<DunningState> {
  const { api } = await getPlatform();
  const reminderDays = String(formData.get("reminder_days") ?? "")
    .split(/[,\s]+/)
    .filter(Boolean)
    .map(Number);
  if (reminderDays.some((day) => !Number.isInteger(day) || day < 0 || day > 60)) return { error: "invalid" };
  const { response } = await api.PUT("/platform/billing/dunning", {
    body: {
      enabled: formData.get("enabled") === "on",
      reminder_days: reminderDays,
      read_only_after_days: Number(formData.get("read_only_after_days")),
      suspend_after_days: Number(formData.get("suspend_after_days")),
    },
  });
  if (!response.ok) return { error: response.status === 422 ? "invalid" : "generic" };
  revalidatePath("/platform/billing");
  return { saved: true };
}
