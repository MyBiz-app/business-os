"use server";

import { getLocale } from "next-intl/server";
import { revalidatePath } from "next/cache";

import { formatMoney } from "@/lib/money";
import { getTenant } from "@/lib/tenant";

export type RunState = { billed?: { id: string; number: number; client: string; total: string }[]; skipped?: number; error?: boolean };

/** Bills the month for the chosen clients at once (#45 billing run). */
export async function runBilling(month: string, _state: RunState, formData: FormData): Promise<RunState> {
  const { api, scope } = await getTenant();
  const locale = await getLocale();
  const clientIds = formData.getAll("client_ids").map(String);
  if (clientIds.length === 0) return { error: true };
  const { data } = await api.POST("/bills/run", { params: scope, body: { month, client_ids: clientIds } });
  if (!data) return { error: true };
  revalidatePath("/bills");
  revalidatePath("/quotes");
  return {
    billed: data.bills.map((bill) => ({ id: bill.id, number: bill.number, client: bill.client_name, total: formatMoney(bill.total, bill.currency, locale) })),
    skipped: data.skipped.length,
  };
}
