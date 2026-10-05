"use server";

import { revalidatePath } from "next/cache";

import { getPlatform } from "@/lib/platform";

export type ActionState = { error?: string; done?: string };

const KNOWN = new Set(["already_void", "forbidden", "not_found", "invalid_days"]);

async function failed(response: Response): Promise<ActionState> {
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const detail = typeof body?.detail === "string" ? body.detail : "";
  return { error: KNOWN.has(detail) ? detail : "generic" };
}

function refresh(id: string) {
  revalidatePath(`/platform/businesses/${id}`);
  revalidatePath("/platform/businesses");
}

export async function extendTrial(id: string, _state: ActionState, formData: FormData): Promise<ActionState> {
  const { api } = await getPlatform();
  const days = Number(formData.get("days")) || 7;
  const { data, response } = await api.POST("/platform/businesses/{tenant_id}/trial", {
    params: { path: { tenant_id: id } },
    body: { days },
  });
  if (!data) return failed(response);
  refresh(id);
  return { done: data.trial_ends_at };
}

export async function setModules(id: string, _state: ActionState, formData: FormData): Promise<ActionState> {
  const { api } = await getPlatform();
  let modules: Record<string, number>;
  try {
    modules = JSON.parse(String(formData.get("modules") ?? "{}"));
  } catch {
    return { error: "generic" };
  }
  const { response } = await api.PUT("/platform/businesses/{tenant_id}/modules", {
    params: { path: { tenant_id: id } },
    body: { modules },
  });
  if (!response.ok) return failed(response);
  refresh(id);
  return { done: "modules" };
}

export async function voidInvoice(id: string, _state: ActionState, formData: FormData): Promise<ActionState> {
  const { api } = await getPlatform();
  const { response } = await api.POST("/platform/invoices/{invoice_id}/void", {
    params: { path: { invoice_id: String(formData.get("invoice") ?? "") } },
    body: { reason: String(formData.get("reason") ?? "") },
  });
  if (!response.ok) return failed(response);
  refresh(id);
  return { done: "void" };
}
