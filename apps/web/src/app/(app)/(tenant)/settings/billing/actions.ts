"use server";

import { revalidatePath } from "next/cache";

import { ApiError, unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

type Brand = "visa" | "mastercard" | "amex";

export async function addTestCard(formData: FormData): Promise<void> {
  const { api, scope } = await getTenant();
  const brand = (String(formData.get("brand") || "visa") as Brand);
  unwrap(await api.POST("/billing/payment-method", { params: scope, body: { brand } }));
  revalidatePath("/settings/billing");
}

export async function removeCard(): Promise<void> {
  const { api, scope } = await getTenant();
  const { response } = await api.DELETE("/billing/payment-method", { params: scope });
  if (!response.ok) throw new ApiError(response.status, "remove card failed");
  revalidatePath("/settings/billing");
}

export async function saveDetails(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  const value = (name: string) => String(formData.get(name) ?? "") || null;
  try {
    unwrap(
      await api.PUT("/billing/details", {
        params: scope,
        body: { billing_name: value("billing_name"), billing_email: value("billing_email"), tax_id: value("tax_id") },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/settings/billing");
  return { saved: true };
}

export async function payInvoice(invoiceId: string): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.POST("/billing/invoices/{invoice_id}/pay", { params: { ...scope, path: { invoice_id: invoiceId } } }));
  revalidatePath("/settings/billing");
  revalidatePath(`/settings/billing/invoices/${invoiceId}`);
}

export async function saveAiSpend(formData: FormData): Promise<void> {
  const { api, scope } = await getTenant();
  const cap = String(formData.get("cap") ?? "").trim();
  const major = cap === "" ? null : Number(cap);
  unwrap(
    await api.PUT("/ai/spend", {
      params: scope,
      body: {
        payg_enabled: formData.get("payg") === "on",
        payg_cap_minor: major === null || Number.isNaN(major) || major < 0 ? null : Math.round(major * 100),
      },
    }),
  );
  revalidatePath("/settings/billing");
}

/** The owner ends the subscription at the end of the paid period; the business is kept. */
export async function cancelSubscription(): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.POST("/billing/cancel", { params: scope }));
  revalidatePath("/settings/billing");
}

/** Takes a cancellation back. */
export async function resumeSubscription(): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.DELETE("/billing/cancel", { params: scope }));
  revalidatePath("/", "layout");
}

export type ExtraAiUsersResult = { ok: true } | { ok: false; error: "ai_users_in_use" | "ai_module_required" | "generic" };

/** Sets how many paid "extra AI user" add-ons the business has. Nothing is charged before payments exist. */
export async function saveExtraAiUsers(count: number): Promise<ExtraAiUsersResult> {
  const { api, scope } = await getTenant();
  const { error } = await api.PUT("/ai/extra-users", { params: scope, body: { extra_ai_users: count } });
  if (!error) {
    revalidatePath("/settings/billing");
    revalidatePath("/ai");
    return { ok: true };
  }
  const detail = (error as { detail?: unknown }).detail;
  return { ok: false, error: detail === "ai_users_in_use" || detail === "ai_module_required" ? detail : "generic" };
}
