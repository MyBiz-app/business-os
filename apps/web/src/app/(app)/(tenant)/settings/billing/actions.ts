"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

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

const REASONS = ["too_expensive", "missing_feature", "not_using", "switched", "other"] as const;
type Reason = (typeof REASONS)[number];

function reasonOf(formData: FormData): Reason | null {
  const value = String(formData.get("reason") ?? "");
  return (REASONS as readonly string[]).includes(value) ? (value as Reason) : null;
}

/** The owner ends the subscription at the end of the paid period; the business is kept. */
export async function cancelSubscription(formData: FormData): Promise<void> {
  const { api, scope } = await getTenant();
  const note = String(formData.get("note") ?? "").trim();
  unwrap(await api.POST("/billing/cancel", { params: scope, body: { reason: reasonOf(formData), note: note || null } }));
  revalidatePath("/settings/billing");
  redirect("/settings/billing?cancelled=1");
}

/** Takes a cancellation back. */
export async function resumeSubscription(): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.DELETE("/billing/cancel", { params: scope }));
  revalidatePath("/", "layout");
}

/** Pauses the account for a few months: the data is kept and everything is read-only. */
export async function pauseSubscription(formData: FormData): Promise<void> {
  const { api, scope } = await getTenant();
  const months = Math.min(3, Math.max(1, Number(formData.get("months")) || 1));
  unwrap(await api.POST("/billing/pause", { params: scope, body: { months, reason: reasonOf(formData) } }));
  revalidatePath("/", "layout");
  redirect("/settings/billing");
}

/** Ends a pause now. */
export async function endPause(): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.DELETE("/billing/pause", { params: scope }));
  revalidatePath("/", "layout");
}
