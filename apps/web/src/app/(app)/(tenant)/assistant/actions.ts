"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiError, unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

export type AskState = { error?: "ai_not_configured" | "ai_busy" | "ai_unavailable" | "generic" };

export async function newConversation(): Promise<void> {
  const { api, scope } = await getTenant();
  const conversation = unwrap(await api.POST("/ai/conversations", { params: scope }));
  redirect(`/assistant?c=${conversation.id}`);
}

export async function askAssistant(conversationId: string, _state: AskState, formData: FormData): Promise<AskState> {
  const question = String(formData.get("text") ?? "").trim();
  if (!question) return {};
  const { api, scope } = await getTenant();
  try {
    unwrap(
      await api.POST("/ai/conversations/{conversation_id}/messages", {
        params: { ...scope, path: { conversation_id: conversationId } },
        body: { text: question },
      }),
    );
  } catch (error) {
    const detail = error instanceof ApiError ? (error.body as { detail?: unknown } | null)?.detail : null;
    if (detail === "ai_not_configured" || detail === "ai_busy" || detail === "ai_unavailable") return { error: detail };
    return { error: "generic" };
  }
  revalidatePath("/assistant");
  return {};
}

export async function decideAction(actionId: string, decision: "confirm" | "reject"): Promise<void> {
  const { api, scope } = await getTenant();
  const params = { ...scope, path: { action_id: actionId } };
  try {
    if (decision === "confirm") unwrap(await api.POST("/ai/pending-actions/{action_id}/confirm", { params }));
    else unwrap(await api.POST("/ai/pending-actions/{action_id}/reject", { params }));
  } catch {
    // The card shows the action's final state (expired, failed) after the refresh.
  }
  revalidatePath("/assistant");
  revalidatePath("/schedule");
}
