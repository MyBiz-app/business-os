"use server";

import { revalidatePath } from "next/cache";
import { RedirectType, redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { toMinorUnits } from "@/lib/money";
import { getTenant } from "@/lib/tenant";

const value = (formData: FormData, name: string) => String(formData.get(name) ?? "");

const CYCLES = ["monthly", "quarterly", "yearly", "custom"] as const;

function readCommon(formData: FormData, currency: string) {
  const price = toMinorUnits(value(formData, "price"), currency);
  if (price === null) return null;
  return {
    name: value(formData, "name"),
    description: value(formData, "description"),
    price_amount: price,
    // A plan with a billing cycle has no validity field: the API sets it from the cycle.
    validity_days: Number(value(formData, "validity_days")) || 30,
    active: formData.get("active") === "on",
  };
}

export async function createPlan(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope, tenant } = await getTenant();
  const common = readCommon(formData, tenant.currency);
  if (!common) return { error: "invalid" };
  const kind = value(formData, "kind") === "punch_card" ? "punch_card" : "membership";
  const cycle = CYCLES.find((option) => option === value(formData, "billing_cycle"));
  const renewing = kind === "membership" && cycle !== undefined;
  try {
    unwrap(
      await api.POST("/plans", {
        params: scope,
        body: {
          ...common,
          kind,
          credits: kind === "punch_card" ? Number(value(formData, "credits")) : null,
          billing_cycle: renewing ? cycle : null,
          billing_cycle_days: renewing && cycle === "custom" ? Number(value(formData, "billing_cycle_days")) : null,
          auto_renew: renewing && formData.get("auto_renew") === "on",
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/catalog");
  return { saved: true };
}

export async function updatePlan(planId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope, tenant } = await getTenant();
  const common = readCommon(formData, tenant.currency);
  if (!common) return { error: "invalid" };
  // Only a plan that has a billing cycle shows the switch; the others leave it as it is.
  const { validity_days: _validity, ...rest } = common;
  const body = {
    ...rest,
    ...(formData.has("validity_days") ? { validity_days: common.validity_days } : {}),
    ...(formData.has("auto_renew_shown") ? { auto_renew: formData.get("auto_renew") === "on" } : {}),
  };
  try {
    unwrap(await api.PATCH("/plans/{plan_id}", { params: { ...scope, path: { plan_id: planId } }, body }));
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/catalog");
  return { saved: true };
}

export async function deletePlan(planId: string): Promise<void> {
  const { api, scope } = await getTenant();
  const { result } = unwrap(await api.DELETE("/plans/{plan_id}", { params: { ...scope, path: { plan_id: planId } } }));
  revalidatePath("/catalog");
  redirect(`/catalog?tab=plans&removed=${result}`, RedirectType.replace);
}
