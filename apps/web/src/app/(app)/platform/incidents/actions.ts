"use server";

import { revalidatePath } from "next/cache";

import { getPlatformFor } from "@/lib/platform";

export type IncidentState = { error?: string; saved?: boolean };

const KINDS = ["incident", "maintenance", "security"] as const;

/** Opens a banner: it shows on every page until it is resolved. */
export async function openIncident(_state: IncidentState, formData: FormData): Promise<IncidentState> {
  const { api } = await getPlatformFor("broadcasts.manage");
  const text = (name: string) => String(formData.get(name) ?? "").trim();
  const kind = KINDS.find((k) => k === text("kind")) ?? "incident";
  const { response } = await api.POST("/platform/incidents", {
    body: {
      kind,
      content: {
        he: { title: text("title_he"), body: text("body_he") },
        en: { title: text("title_en"), body: text("body_en") },
      },
      status_url: text("status_url"),
    },
  });
  if (!response.ok) return { error: response.status === 403 ? "forbidden" : "generic" };
  revalidatePath("/", "layout");
  return { saved: true };
}

export async function resolveIncident(id: string): Promise<IncidentState> {
  const { api } = await getPlatformFor("broadcasts.manage");
  const { response } = await api.POST("/platform/incidents/{incident_id}/resolve", { params: { path: { incident_id: id } } });
  if (!response.ok) return { error: "generic" };
  revalidatePath("/", "layout");
  return { saved: true };
}
