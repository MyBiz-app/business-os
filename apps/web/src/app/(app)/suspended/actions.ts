"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { getApi, unwrap } from "@/lib/api";
import { getActiveMembership } from "@/lib/tenant";

async function scoped() {
  const { membership } = await getActiveMembership();
  if (!membership) redirect("/welcome");
  return { api: await getApi(), params: { header: { "X-Tenant-Id": membership.tenant_id } } };
}

/** Pays every open invoice (with a test card first when there is none: the charges are simulated). */
export async function settleInvoices(): Promise<void> {
  const { api, params } = await scoped();
  const billing = unwrap(await api.GET("/billing", { params }));
  if (!billing.payment_method) unwrap(await api.POST("/billing/payment-method", { params, body: { brand: "visa" } }));
  for (const invoice of billing.invoices.filter((i) => i.status === "open")) {
    unwrap(await api.POST("/billing/invoices/{invoice_id}/pay", { params: { ...params, path: { invoice_id: invoice.id } } }));
  }
  revalidatePath("/", "layout");
  redirect("/dashboard");
}

/** Brings back a business whose subscription ended. */
export async function resumeEndedSubscription(): Promise<void> {
  const { api, params } = await scoped();
  unwrap(await api.DELETE("/billing/cancel", { params }));
  revalidatePath("/", "layout");
  redirect("/dashboard");
}
