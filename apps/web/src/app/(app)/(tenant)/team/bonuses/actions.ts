"use server";

import { revalidatePath } from "next/cache";

import type { components } from "@business-os/api-client";
import { getTenant } from "@/lib/tenant";

export type BonusError = "amount_required" | "no_recipients" | "amount_too_small" | "forbidden" | "invalid" | "generic";
export type BonusResult<T = undefined> = { ok?: true; data?: T; error?: BonusError };
export type BonusInput = components["schemas"]["BonusBody"];
export type BonusPreview = components["schemas"]["BonusPreview"];
export type BonusBatch = components["schemas"]["BonusBatch"];

const KNOWN: BonusError[] = ["no_recipients", "amount_too_small"];

function failure(status: number, body: unknown): { error: BonusError } {
  const detail = (body as { detail?: unknown } | null)?.detail;
  const known = KNOWN.find((code) => code === detail);
  if (known) return { error: known };
  if (status === 403) return { error: "forbidden" };
  return { error: status === 422 ? "invalid" : "generic" };
}

/** Who would get what; nothing is saved. Open to payroll managers and to proposers. */
export async function previewBonus(input: BonusInput): Promise<BonusResult<BonusPreview>> {
  const { api, scope } = await getTenant();
  const response = await api.POST("/payroll/bonuses/preview", { params: scope, body: input });
  if (!response.data) return failure(response.response.status, response.error);
  return { ok: true, data: response.data };
}

export async function addBonus(input: BonusInput): Promise<BonusResult<BonusBatch>> {
  const { api, scope } = await getTenant();
  const response = await api.POST("/payroll/bonuses", { params: scope, body: input });
  if (!response.data) return failure(response.response.status, response.error);
  revalidatePath("/team/bonuses");
  return { ok: true, data: response.data };
}

export async function decideBonus(batchId: string, approve: boolean): Promise<BonusResult> {
  const { api, scope } = await getTenant();
  const response = await api.POST("/payroll/bonuses/{batch_id}/decision", {
    params: { ...scope, path: { batch_id: batchId } },
    body: { approve },
  });
  if (!response.response.ok) return failure(response.response.status, response.error);
  revalidatePath("/team/bonuses");
  return { ok: true };
}

export async function removeAdjustment(adjustmentId: string): Promise<BonusResult> {
  const { api, scope } = await getTenant();
  const response = await api.DELETE("/payroll/adjustments/{adjustment_id}", {
    params: { ...scope, path: { adjustment_id: adjustmentId } },
  });
  if (!response.response.ok) return failure(response.response.status, response.error);
  revalidatePath("/team/bonuses");
  return { ok: true };
}
