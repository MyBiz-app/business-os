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
