"use server";

import { revalidatePath } from "next/cache";

import { errorState, type FormState } from "@/lib/form-state";
import { unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

/** Approves or declines a time-off request; `decision` comes from the pressed button. */
export async function decideRequest(requestId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenantFor("staff.manage");
  const body = { note: String(formData.get("note") ?? "") || null };
  const params = { ...scope, path: { request_id: requestId } };
  try {
    if (formData.get("decision") === "decline") {
      unwrap(await api.POST("/time-off-requests/{request_id}/decline", { params, body }));
    } else {
      unwrap(await api.POST("/time-off-requests/{request_id}/approve", { params, body }));
    }
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/team/time-off");
  return { saved: true };
}
