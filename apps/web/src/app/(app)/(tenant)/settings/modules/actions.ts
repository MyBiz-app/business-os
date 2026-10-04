"use server";

import { revalidatePath } from "next/cache";

import { ApiError, unwrap } from "@/lib/api";
import type { FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

export async function saveModules(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    const modules = JSON.parse(String(formData.get("modules") ?? "{}"));
    unwrap(await api.PUT("/tenants/current/modules", { params: scope, body: { modules } }));
  } catch (error) {
    return { error: error instanceof ApiError && error.status === 422 ? "invalid" : "generic" };
  }
  revalidatePath("/", "layout");
  return { saved: true };
}
