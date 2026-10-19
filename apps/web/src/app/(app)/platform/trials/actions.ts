"use server";

import { revalidatePath } from "next/cache";

import { getPlatform } from "@/lib/platform";

export type TrialState = { error?: string; done?: string };

/** Gives a business whose trial is ending more days (a goodwill gesture, a late start). */
export async function extendFromList(id: string, _state: TrialState, formData: FormData): Promise<TrialState> {
  const { api } = await getPlatform();
  const days = Number(formData.get("days")) || 7;
  const { data, response } = await api.POST("/platform/businesses/{tenant_id}/trial", {
    params: { path: { tenant_id: id } },
    body: { days },
  });
  if (!data) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    return { error: body?.detail === "forbidden" ? "forbidden" : "generic" };
  }
  revalidatePath("/platform/trials");
  revalidatePath(`/platform/businesses/${id}`);
  return { done: data.trial_ends_at };
}
