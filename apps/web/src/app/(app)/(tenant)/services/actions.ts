"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { toMinorUnits } from "@/lib/money";
import { getTenant } from "@/lib/tenant";

function readForm(formData: FormData, currency: string) {
  const value = (name: string) => String(formData.get(name) ?? "");
  const price = toMinorUnits(value("price"), currency);
  if (price === null) return null;
  const mode = (["appointment", "resource"].includes(value("booking_mode")) ? value("booking_mode") : "class") as
    | "class"
    | "appointment"
    | "resource";
  const resource =
    mode === "resource"
      ? {
          min_minutes: Number(value("min_minutes")),
          max_minutes: Number(value("max_minutes")),
          step_minutes: Number(value("step_minutes")),
          price_per_hour: toMinorUnits(value("price_per_hour"), currency),
        }
      : {};
  if (mode === "resource" && resource.price_per_hour === null) return null;
  // An appointment can happen at the client's address, with time to get there (#42).
  const onSite = mode === "appointment" && formData.get("on_site") === "on";
  return {
    ...resource,
    on_site: onSite,
    travel_minutes: onSite ? Number(value("travel_minutes") || 0) : 0,
    name: value("name"),
    description: value("description"),
    duration_minutes: Number(value("duration_minutes")),
    capacity: Number(value("capacity")),
    booking_mode: mode,
    price_amount: price,
    color: value("color"),
    active: formData.get("active") === "on",
  };
}

export async function createService(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope, tenant } = await getTenant();
  const body = readForm(formData, tenant.currency);
  if (!body) return { error: "invalid" };
  try {
    unwrap(await api.POST("/services", { params: scope, body }));
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/services");
  redirect("/services");
}

export async function updateService(
  serviceId: string,
  _state: FormState,
  formData: FormData,
): Promise<FormState> {
  const { api, scope, tenant } = await getTenant();
  const body = readForm(formData, tenant.currency);
  if (!body) return { error: "invalid" };
  try {
    unwrap(
      await api.PATCH("/services/{service_id}", {
        params: { ...scope, path: { service_id: serviceId } },
        body,
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/services");
  return { saved: true };
}

/** Which courts / rooms serve a resource service (replaces the list). */
export async function saveServiceRooms(serviceId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.PUT("/services/{service_id}/rooms", {
        params: { ...scope, path: { service_id: serviceId } },
        body: formData.getAll("room_id").map(String),
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/services/${serviceId}`);
  return { saved: true };
}
