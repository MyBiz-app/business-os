"use server";

import { revalidatePath } from "next/cache";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

type Mode = "off" | "auto" | "first_come" | "manual";
const MODES = ["off", "auto", "first_come", "manual"];
const modeOf = (value: FormDataEntryValue | null, fallback: Mode): Mode => (MODES.includes(String(value)) ? (String(value) as Mode) : fallback);

export async function updateWaitlist(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.PATCH("/tenants/current", {
        params: scope,
        body: {
          waitlist_enabled: formData.get("waitlist_enabled") === "on",
          waitlist_class_mode: modeOf(formData.get("waitlist_class_mode"), "auto"),
          waitlist_appointment_mode: modeOf(formData.get("waitlist_appointment_mode"), "off"),
          waitlist_resource_mode: modeOf(formData.get("waitlist_resource_mode"), "off"),
          waitlist_auto_hours: Number(formData.get("waitlist_auto_hours")) || 0,
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/", "layout");
  return { saved: true };
}

/** One service's own mode; an empty choice goes back to following the business. */
export async function updateServiceWaitlist(serviceId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  const chosen = String(formData.get("waitlist_mode") ?? "");
  try {
    unwrap(
      await api.PATCH("/services/{service_id}", {
        params: { ...scope, path: { service_id: serviceId } },
        body: { waitlist_mode: MODES.includes(chosen) ? (chosen as Mode) : null },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/settings/bookings");
  return { saved: true };
}
