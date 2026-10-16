"use server";

import type { components } from "@business-os/api-client";
import { revalidatePath } from "next/cache";

import { getPlatformFor } from "@/lib/platform";

export type BroadcastBody = components["schemas"]["AnnouncementBody"];
export type AudienceBody = components["schemas"]["Audience"];
export type Preview = components["schemas"]["Preview"];
export type BroadcastResult = { error?: string; id?: string; notice?: "saved" | "scheduled" | "cancelled" | "deleted"; testedTo?: string; tested?: boolean };

const KNOWN = new Set(["audience_required", "content_required", "already_sent", "forbidden"]);

async function errorOf(response: Response): Promise<BroadcastResult> {
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const detail = typeof body?.detail === "string" ? body.detail : "";
  return { error: KNOWN.has(detail) ? detail : "generic" };
}

/** The live count of who would get it. */
export async function previewAudience(kind: BroadcastBody["kind"], audience: AudienceBody): Promise<Preview | null> {
  const { api } = await getPlatformFor("broadcasts.manage");
  const { data } = await api.POST("/platform/broadcasts/preview", { body: { kind, audience } });
  return data ?? null;
}

/** Saves a draft: a new one when `id` is empty. */
export async function saveBroadcast(id: string | null, body: BroadcastBody): Promise<BroadcastResult> {
  const { api } = await getPlatformFor("broadcasts.manage");
  const { data, response } = id
    ? await api.PUT("/platform/broadcasts/{announcement_id}", { params: { path: { announcement_id: id } }, body })
    : await api.POST("/platform/broadcasts", { body });
  if (!response.ok || !data) return errorOf(response);
  revalidatePath("/platform/broadcasts");
  return { id: data.id, notice: "saved" };
}

/** Saves what is on screen, then schedules it (without a time: the next run). */
export async function scheduleBroadcast(id: string | null, body: BroadcastBody, at: string | null): Promise<BroadcastResult> {
  const saved = await saveBroadcast(id, body);
  if (saved.error || !saved.id) return saved;
  const { api } = await getPlatformFor("broadcasts.manage");
  const { response } = await api.POST("/platform/broadcasts/{announcement_id}/schedule", {
    params: { path: { announcement_id: saved.id } },
    body: { scheduled_at: at },
  });
  if (!response.ok) return { ...(await errorOf(response)), id: saved.id };
  revalidatePath("/platform/broadcasts");
  return { id: saved.id, notice: "scheduled" };
}

/** Saves what is on screen, then sends the email version to the signed-in team member. */
export async function sendTest(id: string | null, body: BroadcastBody): Promise<BroadcastResult> {
  const saved = await saveBroadcast(id, body);
  if (saved.error || !saved.id) return saved;
  const { api } = await getPlatformFor("broadcasts.manage");
  const { data, response } = await api.POST("/platform/broadcasts/{announcement_id}/test", {
    params: { path: { announcement_id: saved.id } },
  });
  if (!response.ok || !data) return { ...(await errorOf(response)), id: saved.id };
  return { id: saved.id, tested: data.email, testedTo: data.sent_to };
}

export async function cancelBroadcast(id: string): Promise<BroadcastResult> {
  const { api } = await getPlatformFor("broadcasts.manage");
  const { response } = await api.POST("/platform/broadcasts/{announcement_id}/cancel", { params: { path: { announcement_id: id } } });
  if (!response.ok) return errorOf(response);
  revalidatePath("/platform/broadcasts");
  return { id, notice: "cancelled" };
}

export async function deleteBroadcast(id: string): Promise<BroadcastResult> {
  const { api } = await getPlatformFor("broadcasts.manage");
  const { response } = await api.DELETE("/platform/broadcasts/{announcement_id}", { params: { path: { announcement_id: id } } });
  if (!response.ok) return errorOf(response);
  revalidatePath("/platform/broadcasts");
  return { notice: "deleted" };
}
