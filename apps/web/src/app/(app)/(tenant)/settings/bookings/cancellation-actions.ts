"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

type Outcome = "counts" | "recorded";
const outcomeOf = (value: FormDataEntryValue | null): Outcome => (value === "recorded" ? "recorded" : "counts");
const minutesOf = (value: FormDataEntryValue | null) => Math.max(0, Math.min(10080, Number(value) || 0));
const limitOf = (value: FormDataEntryValue | null) => {
  const n = Number(value);
  return Number.isFinite(n) && n >= 1 ? Math.min(30, Math.floor(n)) : null;
};

/** The business's own terms: how long before a class, a personal session and a court or room a
 * client may cancel for free, and what a late cancellation or a no-show costs. */
export async function saveCancellationPolicy(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.PUT("/cancellation-policy", {
        params: scope,
        body: {
          group_minutes: minutesOf(formData.get("group_minutes")),
          personal_minutes: minutesOf(formData.get("personal_minutes")),
          resource_minutes: minutesOf(formData.get("resource_minutes")),
          late_outcome: outcomeOf(formData.get("late_outcome")),
          no_show_outcome: outcomeOf(formData.get("no_show_outcome")),
          no_show_limit: formData.get("limit_on") === "on" ? limitOf(formData.get("no_show_limit")) : null,
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/settings", "layout");
  revalidatePath("/dashboard");
  return { saved: true };
}

/** One service's or plan's own terms; an empty window goes back to following the business. */
export async function saveOverride(
  scope_: "service" | "plan",
  id: string,
  _state: FormState,
  formData: FormData,
): Promise<FormState> {
  const { api, scope } = await getTenant();
  const raw = String(formData.get("free_minutes") ?? "");
  try {
    if (raw === "") {
      if (scope_ === "service") {
        unwrap(await api.DELETE("/services/{service_id}/cancellation-policy", { params: { ...scope, path: { service_id: id } } }));
      } else {
        unwrap(await api.DELETE("/plans/{plan_id}/cancellation-policy", { params: { ...scope, path: { plan_id: id } } }));
      }
    } else {
      const body = {
        free_minutes: minutesOf(raw),
        late_outcome: outcomeOf(formData.get("late_outcome")),
        no_show_outcome: outcomeOf(formData.get("no_show_outcome")),
        no_show_limit: null,
      };
      if (scope_ === "service") {
        unwrap(await api.PUT("/services/{service_id}/cancellation-policy", { params: { ...scope, path: { service_id: id } }, body }));
      } else {
        unwrap(await api.PUT("/plans/{plan_id}/cancellation-policy", { params: { ...scope, path: { plan_id: id } }, body }));
      }
    }
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/settings", "layout");
  return { saved: true };
}
