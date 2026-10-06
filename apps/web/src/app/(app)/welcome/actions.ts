"use server";

import { redirect } from "next/navigation";

import { getApi, unwrap } from "@/lib/api";
import { setActiveTenant } from "@/lib/tenant";

export type SampleState = { error?: boolean };

/** Creates a sample business with fictitious data (POST /tenants/sample) and opens it. */
export async function exploreSample(_state: SampleState, formData: FormData): Promise<SampleState> {
  let tenantId: string;
  try {
    const vertical = String(formData.get("vertical") ?? "");
    tenantId = unwrap(await (await getApi()).POST("/tenants/sample", { body: { vertical } })).tenant_id;
  } catch {
    return { error: true };
  }
  await setActiveTenant(tenantId);
  redirect("/dashboard?sample=1");
}
