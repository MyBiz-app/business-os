"use server";

import { getLocale } from "next-intl/server";
import { redirect } from "next/navigation";

import { ApiError, getApi, type Tenant, unwrap } from "@/lib/api";
import { decodePlan } from "@/lib/signup-plan";
import { setActiveTenant } from "@/lib/tenant";

export type FinishState = { error?: "invalid" | "generic" };

const BRANDS = ["visa", "mastercard", "amex"] as const;

/** The end of the sign-up journey: creates the business with the chosen modules, puts the
 * (simulated) card on file, sends the welcome email and opens the dashboard. */
export async function startTrial(_state: FinishState, formData: FormData): Promise<FinishState> {
  const plan = decodePlan(formData.get("plan"));
  if (!plan) return { error: "invalid" };
  const timeZone = String(formData.get("time_zone") ?? "");
  const supported = Intl.supportedValuesOf("timeZone");
  const locale = (await getLocale()) === "en" ? "en" : "he";
  const fallbackZone = locale === "he" ? "Asia/Jerusalem" : "America/New_York";
  const brandField = String(formData.get("brand") ?? "");
  const brand = (BRANDS as readonly string[]).includes(brandField) ? (brandField as (typeof BRANDS)[number]) : "visa";

  const api = await getApi();
  let tenant: Tenant;
  try {
    tenant = unwrap(
      await api.POST("/tenants", {
        body: {
          name: plan.name,
          vertical: plan.vertical,
          locale,
          time_zone: supported.includes(timeZone) ? timeZone : fallbackZone,
          currency: plan.currency,
          modules: plan.modules,
        },
      }),
    );
  } catch (error) {
    return { error: error instanceof ApiError && error.status === 422 ? "invalid" : "generic" };
  }
  await setActiveTenant(tenant.id);

  // The business exists from here on; a hiccup in the steps below must not block the owner.
  const scope = { header: { "X-Tenant-Id": tenant.id } };
  await api.POST("/billing/payment-method", { params: scope, body: { brand } }).catch(() => null);
  await api
    .POST("/tenants/current/welcome-email", { params: scope, body: { expected_active_clients: plan.clients } })
    .catch(() => null);
  redirect("/dashboard?welcome=1");
}
