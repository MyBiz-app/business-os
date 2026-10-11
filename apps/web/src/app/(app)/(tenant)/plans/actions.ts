"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { toMinorUnits } from "@/lib/money";
import { getTenant } from "@/lib/tenant";

const value = (formData: FormData, name: string) => String(formData.get(name) ?? "");

function readCommon(formData: FormData, currency: string) {
  const price = toMinorUnits(value(formData, "price"), currency);
  if (price === null) return null;
  return {
    name: value(formData, "name"),
    description: value(formData, "description"),
    price_amount: price,
    validity_days: Number(value(formData, "validity_days")),
    active: formData.get("active") === "on",
  };
}

export async function createPlan(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope, tenant } = await getTenant();
  const common = readCommon(formData, tenant.currency);
  if (!common) return { error: "invalid" };
  const kind = value(formData, "kind") === "punch_card" ? "punch_card" : "membership";
  try {
    unwrap(
      await api.POST("/plans", {
        params: scope,
        body: { ...common, kind, credits: kind === "punch_card" ? Number(value(formData, "credits")) : null },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/plans");
  redirect("/plans");
}

export async function updatePlan(planId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope, tenant } = await getTenant();
  const body = readCommon(formData, tenant.currency);
  if (!body) return { error: "invalid" };
  try {
    unwrap(await api.PATCH("/plans/{plan_id}", { params: { ...scope, path: { plan_id: planId } }, body }));
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/plans");
  return { saved: true };
}

export async function deletePlan(planId: string): Promise<void> {
  const { api, scope } = await getTenant();
  const { result } = unwrap(await api.DELETE("/plans/{plan_id}", { params: { ...scope, path: { plan_id: planId } } }));
  revalidatePath("/plans");
  redirect(`/plans?removed=${result}`);
}
