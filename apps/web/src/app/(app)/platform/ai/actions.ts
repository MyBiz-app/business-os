"use server";

import { revalidatePath } from "next/cache";

import { getPlatform } from "@/lib/platform";

export type AiState = { error?: string; saved?: boolean };

const KNOWN = new Set(["model_not_available", "model_wrong_tier", "reason_required", "forbidden"]);

async function errorOf(response: Response): Promise<AiState> {
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const detail = typeof body?.detail === "string" ? body.detail : "";
  return { error: KNOWN.has(detail) ? detail : "generic" };
}

const model = (data: FormData, name: string) => String(data.get(name) ?? "") || null;

/** Chooses the model for each tier and flips the emergency stop for every business. */
export async function saveAiSettings(_state: AiState, formData: FormData): Promise<AiState> {
  const { api } = await getPlatform();
  const { response } = await api.PUT("/platform/ai/settings", {
    body: {
      kill_all: formData.get("kill_all") === "on",
      model_fast: model(formData, "model_fast"),
      model_standard: model(formData, "model_standard"),
      model_strong: model(formData, "model_strong"),
    },
  });
  if (!response.ok) return errorOf(response);
  revalidatePath("/platform/ai");
  return { saved: true };
}

/** Stops AI for one business (with a reason) or lets it run again. */
export async function setBusinessAiPaused(tenantId: string, paused: boolean, reason: string): Promise<AiState> {
  const { api } = await getPlatform();
  const { response } = await api.POST("/platform/ai/businesses/{tenant_id}/pause", {
    params: { path: { tenant_id: tenantId } },
    body: { paused, reason: paused ? reason : null },
  });
  if (!response.ok) return errorOf(response);
  revalidatePath("/platform/ai");
  return { saved: true };
}

export type ChatRole = "manager" | "support" | "health" | "billing" | "growth";
export type ChatTurn = { role: "user" | "assistant"; text: string };
export type ChatResult = { id?: string; turns?: ChatTurn[]; error?: string };

/** One question to the console assistant; opens the conversation on the first one. */
export async function askConsoleAssistant(chatId: string | null, role: ChatRole, text: string): Promise<ChatResult> {
  const { api } = await getPlatform();
  let id = chatId;
  if (!id) {
    const started = await api.POST("/platform/ai/assistant/conversations", { body: { role } });
    if (!started.data) return { error: "generic" };
    id = started.data.id;
  }
  const { data, response } = await api.POST("/platform/ai/assistant/conversations/{chat_id}/messages", {
    params: { path: { chat_id: id } },
    body: { text },
  });
  if (!data) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = typeof body?.detail === "string" ? body.detail : "";
    const known = ["ai_paused", "conversation_limit", "ai_busy", "ai_unavailable", "ai_not_configured"];
    return { id, error: known.includes(detail) ? detail : "generic" };
  }
  return { id: data.id, turns: data.turns };
}

export type ChatOpened = { id: string; role: ChatRole; turns: ChatTurn[] };

/** An earlier conversation of the signed-in team member, with its turns. */
export async function openConsoleChat(chatId: string): Promise<ChatOpened | null> {
  const { api } = await getPlatform();
  const { data } = await api.GET("/platform/ai/assistant/conversations/{chat_id}", { params: { path: { chat_id: chatId } } });
  return data ? { id: data.id, role: data.role, turns: data.turns } : null;
}
