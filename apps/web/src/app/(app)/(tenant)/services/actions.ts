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
  return {
    name: value("name"),
    description: value("description"),
    duration_minutes: Number(value("duration_minutes")),
    capacity: Number(value("capacity")),
    booking_mode: (value("booking_mode") === "appointment" ? "appointment" : "class") as "class" | "appointment",
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
