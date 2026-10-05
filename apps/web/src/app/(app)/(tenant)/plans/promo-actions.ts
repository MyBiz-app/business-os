"use server";

import { revalidatePath } from "next/cache";

import { ApiError, unwrap } from "@/lib/api";
import { toMinorUnits } from "@/lib/money";
import { getTenant } from "@/lib/tenant";

export type PromoState = { saved?: boolean; error?: "invalid" | "code_taken" | "generic" };

export async function createPromoCode(_state: PromoState, formData: FormData): Promise<PromoState> {
  const { api, scope } = await getTenant();
  const value = (name: string) => String(formData.get(name) ?? "").trim();
  const kind = value("kind");
  const amount = kind === "amount" ? toMinorUnits(value("value")) : null;
  const percent = kind === "percent" ? Number(value("value")) : null;
  if ((kind === "amount" && !amount) || (kind === "percent" && !(percent && percent >= 1 && percent <= 100))) {
    return { error: "invalid" };
  }
  try {
    unwrap(
      await api.POST("/promo-codes", {
        params: scope,
        body: {
          code: value("code"),
          percent_off: percent,
          amount_off: amount,
          plan_id: value("plan_id") || null,
          starts_on: value("starts_on") || null,
          ends_on: value("ends_on") || null,
          max_uses: value("max_uses") ? Number(value("max_uses")) : null,
        },
      }),
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) return { error: "code_taken" };
    if (error instanceof ApiError && error.status === 422) return { error: "invalid" };
    return { error: "generic" };
  }
  revalidatePath("/plans");
  return { saved: true };
}

export async function setPromoActive(codeId: string, active: boolean): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.PATCH("/promo-codes/{code_id}", { params: { ...scope, path: { code_id: codeId } }, body: { active } }));
  revalidatePath("/plans");
}

export async function deletePromoCode(codeId: string): Promise<void> {
  const { api, scope } = await getTenant();
  const { response } = await api.DELETE("/promo-codes/{code_id}", { params: { ...scope, path: { code_id: codeId } } });
  if (!response.ok && response.status !== 409) throw new ApiError(response.status, "delete promo failed");
  revalidatePath("/plans");
}
