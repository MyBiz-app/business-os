"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { apiFetch, unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { toMinorUnits } from "@/lib/money";
import { getTenant } from "@/lib/tenant";

/** Uploads a document to the client's card (#45). */
export async function uploadDocument(clientId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { tenant } = await getTenant();
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) return { error: "invalid" };
  const body = new FormData();
  body.set("file", file);
  body.set("name", String(formData.get("name") || file.name));
  body.set("kind", String(formData.get("kind") ?? "other"));
  body.set("shared", formData.get("shared") === "on" ? "true" : "false");
  body.set("sign_requested", formData.get("sign_requested") === "on" ? "true" : "false");
  const response = await apiFetch(`/clients/${encodeURIComponent(clientId)}/documents`, { method: "POST", body }, tenant.id);
  if (!response.ok) return { error: response.status === 422 ? "invalid" : "generic" };
  revalidatePath(`/clients/${clientId}`);
  return { saved: true };
}

export async function updateDocument(
  clientId: string,
  documentId: string,
  change: { shared?: boolean; sign_requested?: boolean },
): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.PATCH("/documents/{document_id}", { params: { ...scope, path: { document_id: documentId } }, body: change }));
  revalidatePath(`/clients/${clientId}`);
}

export async function deleteDocument(clientId: string, documentId: string): Promise<void> {
  const { api, scope } = await getTenant();
  await api.DELETE("/documents/{document_id}", { params: { ...scope, path: { document_id: documentId } } });
  revalidatePath(`/clients/${clientId}`);
}

/** Logs the signed-in staff member's time for a client. */
export async function logTime(clientId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  const hours = Number(String(formData.get("hours") ?? "0").replace(",", "."));
  const minutes = Math.round(hours * 60);
  if (!(minutes > 0)) return { error: "invalid" };
  try {
    unwrap(
      await api.POST("/time", {
        params: scope,
        body: {
          client_id: clientId,
          day: String(formData.get("day") ?? ""),
          minutes,
          description: String(formData.get("description") ?? ""),
          billable: formData.get("billable") === "on",
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/clients/${clientId}`);
  revalidatePath("/time");
  return { saved: true };
}

export async function saveRetainer(clientId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope, tenant } = await getTenant();
  const monthly = toMinorUnits(String(formData.get("monthly") || "0"), tenant.currency);
  const rate = toMinorUnits(String(formData.get("rate") || "0"), tenant.currency);
  const included = Math.round(Number(String(formData.get("included_hours") || "0").replace(",", ".")) * 60);
  if (monthly === null || rate === null || !(included >= 0)) return { error: "invalid" };
  try {
    unwrap(
      await api.PUT("/clients/{client_id}/retainer", {
        params: { ...scope, path: { client_id: clientId } },
        body: { monthly_amount: monthly, included_minutes: included, hourly_rate: rate, active: true },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath(`/clients/${clientId}`);
  return { saved: true };
}

export type BillState = FormState & { nothing?: boolean };

/** Bills a month of the client's retainer and time, then opens the bill. */
export async function billMonth(clientId: string, _state: BillState, formData: FormData): Promise<BillState> {
  const { api, scope } = await getTenant();
  const { data, response } = await api.POST("/clients/{client_id}/bills", {
    params: { ...scope, path: { client_id: clientId } },
    body: { month: String(formData.get("month") ?? "") },
  });
  if (!data) return response.status === 409 ? { nothing: true } : { error: "generic" };
  revalidatePath(`/clients/${clientId}`);
  redirect(`/quotes/${data.id}`);
}
