"use server";

import type { components } from "@business-os/api-client";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

type LeadSource = components["schemas"]["LeadCreate"]["source"];
type Stage = components["schemas"]["StageChange"]["stage"];
type ActivityKind = components["schemas"]["ActivityCreate"]["kind"];

function readForm(formData: FormData) {
  const value = (name: string) => String(formData.get(name) ?? "");
  return {
    first_name: value("first_name"),
    last_name: value("last_name"),
    email: value("email"),
    phone: value("phone"),
    interest: value("interest"),
    campaign: value("campaign"),
    follow_up_on: value("follow_up_on") || null,
    owner_user_id: value("owner_user_id") || null,
    source: (value("source") || "manual") as LeadSource,
  };
}

function refresh(leadId?: string) {
  revalidatePath("/leads");
  if (leadId) revalidatePath(`/leads/${leadId}`);
}

export async function createLead(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  let id: string;
  try {
    id = unwrap(await api.POST("/leads", { params: scope, body: readForm(formData) })).id;
  } catch (error) {
    return errorState(error);
  }
  refresh();
  redirect(`/leads/${id}`);
}

export async function updateLead(leadId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.PATCH("/leads/{lead_id}", {
        params: { ...scope, path: { lead_id: leadId } },
        body: readForm(formData),
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  refresh(leadId);
  return { saved: true };
}

export async function changeStage(leadId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/leads/{lead_id}/stage", {
        params: { ...scope, path: { lead_id: leadId } },
        body: {
          stage: String(formData.get("stage")) as Stage,
          lost_reason: String(formData.get("lost_reason") ?? "") || null,
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  refresh(leadId);
  return { saved: true };
}

export async function addActivity(leadId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/leads/{lead_id}/activities", {
        params: { ...scope, path: { lead_id: leadId } },
        body: {
          kind: String(formData.get("kind")) as ActivityKind,
          note: String(formData.get("note") ?? ""),
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  refresh(leadId);
  return { saved: true };
}

export async function convertLead(leadId: string): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.POST("/leads/{lead_id}/convert", { params: { ...scope, path: { lead_id: leadId } } }));
  refresh(leadId);
  revalidatePath("/clients");
}

export async function deleteLead(leadId: string): Promise<void> {
  const { api, scope } = await getTenant();
  const { response } = await api.DELETE("/leads/{lead_id}", { params: { ...scope, path: { lead_id: leadId } } });
  if (!response.ok) throw new Error(`delete failed: ${response.status}`);
  refresh();
  redirect("/leads");
}
