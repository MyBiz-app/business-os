"use server";

import { revalidatePath } from "next/cache";

import { apiUpload, unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

export type LogoState = { error?: "logo_too_large" | "unsupported_image" | "generic"; saved?: boolean };

export async function updateDetails(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  const value = (name: string) => String(formData.get(name) ?? "");
  try {
    unwrap(
      await api.PATCH("/tenants/current", {
        params: scope,
        body: {
          name: value("name"),
          locale: value("locale") === "en" ? "en" : "he",
          time_zone: value("time_zone"),
          currency: value("currency"),
          cancellation_window_minutes: Number(value("cancellation_window_minutes")),
          booking_requires_plan: formData.get("booking_requires_plan") === "on",
          requires_health_declaration: formData.get("requires_health_declaration") === "on",
          online_sales: formData.get("online_sales") === "on",
          resource_payment: value("resource_payment") === "venue" ? "venue" : "app",
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/", "layout");
  return { saved: true };
}

export async function updateBrandColor(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  const color = formData.get("use_default") === "on" ? null : String(formData.get("primary_color"));
  try {
    unwrap(await api.PATCH("/tenants/current", { params: scope, body: { primary_color: color } }));
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/", "layout");
  return { saved: true };
}

export async function uploadLogo(_state: LogoState, formData: FormData): Promise<LogoState> {
  const file = formData.get("logo");
  if (!(file instanceof File) || file.size === 0) return { error: "unsupported_image" };
  const { tenant } = await getTenant();
  const response = await apiUpload("/tenants/current/logo", file, tenant.id);
  if (response.status === 413) return { error: "logo_too_large" };
  if (response.status === 415) return { error: "unsupported_image" };
  if (!response.ok) return { error: "generic" };
  revalidatePath("/", "layout");
  return { saved: true };
}

export async function removeLogo(): Promise<void> {
  const { api, scope } = await getTenant();
  await api.DELETE("/tenants/current/logo", { params: scope });
  revalidatePath("/", "layout");
}
