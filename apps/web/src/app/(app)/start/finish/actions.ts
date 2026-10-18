"use server";

import { getLocale } from "next-intl/server";
import { redirect } from "next/navigation";
import { legalVersion } from "@business-os/i18n/brand";

import { addressFromForm } from "@/lib/address";
import { ApiError, getApi, type Tenant, unwrap } from "@/lib/api";
import { clearResumePath } from "@/lib/resume";
import { businessSize, decodePlan } from "@/lib/signup-plan";
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

  const websiteOnly = plan.track === "website_only";
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
          modules: websiteOnly ? {} : plan.modules,
          // A website-only business has no system yet; the size is the journey's staff and branches.
          product_track: websiteOnly ? "website_only" : "full",
          ...(websiteOnly ? {} : { business_size: businessSize(plan.staff, plan.locations) }),
          accepted_legal: { terms: legalVersion("terms"), privacy: legalVersion("privacy"), dpa: legalVersion("dpa") },
        },
      }),
    );
  } catch (error) {
    return { error: error instanceof ApiError && error.status === 422 ? "invalid" : "generic" };
  }
  await setActiveTenant(tenant.id);
  await clearResumePath().catch(() => null);

  // The business exists from here on; a hiccup in the steps below must not block the owner.
  const scope = { header: { "X-Tenant-Id": tenant.id } };
  if (plan.businessNumber || plan.entityType || plan.websiteUrl) {
    await api
      .PATCH("/tenants/current", {
        params: scope,
        body: {
          business_number: plan.businessNumber,
          legal_entity_type: plan.entityType,
          ...(plan.websiteUrl ? { website_url: plan.websiteUrl } : {}),
        },
      })
      .catch(() => null);
  }
  // The main branch starts without an address: the sign-up collects it here (a hiccup is not fatal;
  // the owner can add it in the branch settings, and the setup checklist shows it is missing).
  const address = addressFromForm(formData);
  if (address.city_code) {
    const main = (await api.GET("/locations", { params: scope }).catch(() => null))?.data?.[0];
    if (main) await api.PATCH("/locations/{location_id}", { params: { ...scope, path: { location_id: main.id } }, body: address }).catch(() => null);
  }
  await api.POST("/billing/payment-method", { params: scope, body: { brand } }).catch(() => null);
  if (!websiteOnly) {
    await api
      .POST("/tenants/current/welcome-email", { params: scope, body: { expected_active_clients: plan.clients } })
      .catch(() => null);
  }
  // Whoever asked for a website goes straight to the brief, with what is known already filled in.
  redirect(websiteOnly || plan.site === "build" ? "/website/brief" : "/dashboard?welcome=1");
}
