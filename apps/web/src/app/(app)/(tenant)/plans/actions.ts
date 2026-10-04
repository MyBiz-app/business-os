"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { toMinorUnits } from "@/lib/money";
import { getTenant } from "@/lib/tenant";

const value = (formData: FormData, name: string) => String(formData.get(name) ?? "");

function readCommon(formData: FormData) {
  const price = toMinorUnits(value(formData, "price"));
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
  const common = readCommon(formData);
  if (!common) return { error: "invalid" };
  const kind = value(formData, "kind") === "punch_card" ? "punch_card" : "membership";
  const { api, scope } = await getTenant();
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
  const body = readCommon(formData);
  if (!body) return { error: "invalid" };
  const { api, scope } = await getTenant();
  try {
    unwrap(await api.PATCH("/plans/{plan_id}", { params: { ...scope, path: { plan_id: planId } }, body }));
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/plans");
  return { saved: true };
}
