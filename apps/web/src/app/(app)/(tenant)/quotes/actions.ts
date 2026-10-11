"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { toMinorUnits } from "@/lib/money";
import { getTenant } from "@/lib/tenant";

/** The editor's values: lines come as line.<i>.description / quantity / price. */
function readQuote(formData: FormData, currency: string) {
  const value = (name: string) => String(formData.get(name) ?? "").trim();
  const indexes = new Set<number>();
  for (const name of formData.keys()) {
    const match = /^line\.(\d+)\./.exec(name);
    if (match) indexes.add(Number(match[1]));
  }
  const lines = [...indexes]
    .sort((a, b) => a - b)
    .map((i) => ({
      description: value(`line.${i}.description`),
      quantity: Number(value(`line.${i}.quantity`) || "1"),
      unit_price: toMinorUnits(value(`line.${i}.price`) || "0", currency),
    }))
    .filter((line) => line.description);
  if (lines.length === 0 || lines.some((l) => l.unit_price === null || !(l.quantity > 0))) return null;
  return {
    title: value("title"),
    lines: lines as { description: string; quantity: number; unit_price: number }[],
    deposit_percent: Number(value("deposit_percent") || "0"),
    valid_until: value("valid_until") || null,
    event_date: value("event_date") || null,
    event_time: value("event_time") || null,
    event_place: value("event_place") || null,
    notes: value("notes") || null,
  };
}

export async function createQuote(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope, tenant } = await getTenant();
  const body = readQuote(formData, tenant.currency);
  const clientId = String(formData.get("client_id") ?? "");
  if (!body || !clientId) return { error: "invalid" };
  let id: string;
  try {
    id = unwrap(await api.POST("/quotes", { params: scope, body: { ...body, client_id: clientId } })).id;
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/quotes");
  redirect(`/quotes/${id}`);
}

export async function updateQuote(quoteId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope, tenant } = await getTenant();
  const body = readQuote(formData, tenant.currency);
  if (!body) return { error: "invalid" };
  try {
    unwrap(await api.PUT("/quotes/{quote_id}", { params: { ...scope, path: { quote_id: quoteId } }, body }));
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/quotes/${quoteId}`);
  redirect(`/quotes/${quoteId}`);
}

export async function sendQuote(quoteId: string): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.POST("/quotes/{quote_id}/send", { params: { ...scope, path: { quote_id: quoteId } } }));
  revalidatePath(`/quotes/${quoteId}`);
  revalidatePath("/quotes");
}

export async function copyQuote(quoteId: string): Promise<void> {
  const { api, scope } = await getTenant();
  const copy = unwrap(await api.POST("/quotes/{quote_id}/copy", { params: { ...scope, path: { quote_id: quoteId } } }));
  revalidatePath("/quotes");
  redirect(`/quotes/${copy.id}/edit`);
}

export async function recordQuotePayment(quoteId: string, key: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope, tenant } = await getTenant();
  const amount = toMinorUnits(String(formData.get("amount") ?? ""), tenant.currency);
  if (!amount || amount <= 0) return { error: "invalid" };
  const method = String(formData.get("method") ?? "cash") as "cash" | "card" | "transfer" | "other";
  try {
    unwrap(
      await api.POST("/quotes/{quote_id}/payments", {
        params: { ...scope, path: { quote_id: quoteId } },
        body: { amount, method, idempotency_key: key },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/quotes/${quoteId}`);
  return { saved: true };
}
