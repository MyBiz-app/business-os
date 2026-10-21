"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { toMinorUnits } from "@/lib/money";
import { getTenant } from "@/lib/tenant";

const REASONS = ["travel", "reserve_duty", "illness", "pregnancy", "other"] as const;

export async function saveFreezeRules(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope, tenant } = await getTenant();
  const value = (name: string) => String(formData.get(name) ?? "").trim();
  const fee = toMinorUnits(value("fee") || "0", tenant.currency);
  if (fee === null) return { error: "invalid" };
  try {
    unwrap(
      await api.PUT("/freeze-rules", {
        params: scope,
        body: {
          allow_requests: formData.get("allow_requests") === "on",
          min_days: Number(value("min_days")) || 1,
          max_days: Number(value("max_days")) || 30,
          yearly_bank_days: value("yearly_bank_days") ? Number(value("yearly_bank_days")) : null,
          notice_days: Number(value("notice_days")) || 0,
          fee_amount: fee,
          billing_mode: value("billing_mode") === "credit" ? "credit" : "defer",
          auto_approve_reasons: REASONS.filter((reason) => formData.get(`auto_${reason}`) === "on"),
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/settings", "layout");
  return { saved: true };
}
