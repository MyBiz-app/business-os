"use server";

import { revalidatePath } from "next/cache";

import { ApiError, unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

export type PlanFormState = {
  error?: "invalid" | "generic" | "not_active" | "outside_validity" | "overlapping_freeze";
  saved?: boolean;
  /** After a sale: the idempotency key for the next one. */
  nextKey?: string;
};

function toState(error: unknown): PlanFormState {
  if (error instanceof ApiError) {
    const detail = (error.body as { detail?: unknown } | null)?.detail;
    if (detail === "not_active" || detail === "outside_validity" || detail === "overlapping_freeze") {
      return { error: detail };
    }
    if (error.status === 422) return { error: "invalid" };
  }
  return { error: "generic" };
}

const value = (formData: FormData, name: string) => String(formData.get(name) ?? "").trim();

export async function sellPlan(clientId: string, _state: PlanFormState, formData: FormData): Promise<PlanFormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/clients/{client_id}/entitlements", {
        params: { ...scope, path: { client_id: clientId } },
        body: {
          plan_id: value(formData, "plan_id"),
          starts_on: value(formData, "starts_on") || null,
          idempotency_key: value(formData, "idempotency_key"),
        },
      }),
    );
  } catch (error) {
    return toState(error);
  }
  revalidatePath(`/clients/${clientId}`);
  return { saved: true, nextKey: `sale-${crypto.randomUUID()}` };
}

export async function freezeEntitlement(
  clientId: string,
  entitlementId: string,
  _state: PlanFormState,
  formData: FormData,
): Promise<PlanFormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/entitlements/{entitlement_id}/freezes", {
        params: { ...scope, path: { entitlement_id: entitlementId } },
        body: {
          starts_on: value(formData, "starts_on"),
          ends_on: value(formData, "ends_on"),
          reason: value(formData, "reason") || null,
        },
      }),
    );
  } catch (error) {
    return toState(error);
  }
  revalidatePath(`/clients/${clientId}`);
  return { saved: true };
}

export async function cancelEntitlement(clientId: string, entitlementId: string): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(
    await api.POST("/entitlements/{entitlement_id}/cancel", {
      params: { ...scope, path: { entitlement_id: entitlementId } },
    }),
  );
  revalidatePath(`/clients/${clientId}`);
}
