"use server";

import { revalidatePath } from "next/cache";

import { errorState, type FormState } from "@/lib/form-state";
import { unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

/** Approves or declines a shift swap; `decision` comes from the pressed button. */
export async function decideSwap(swapId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenantFor("staff.manage");
  const body = { note: String(formData.get("note") ?? "") || null };
  const params = { ...scope, path: { swap_id: swapId } };
  try {
    if (formData.get("decision") === "decline") {
      unwrap(await api.POST("/shift-swaps/{swap_id}/decline", { params, body }));
    } else {
      unwrap(await api.POST("/shift-swaps/{swap_id}/approve", { params, body }));
    }
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/team/shift-swaps");
  revalidatePath("/team/shifts");
  return { saved: true };
}
