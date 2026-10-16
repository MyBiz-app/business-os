"use server";

import { revalidatePath } from "next/cache";

import type { components } from "@business-os/api-client";

import { ApiError, unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

export type Conversation = components["schemas"]["app__api__assistant__Conversation"];
export type ConversationSummary = components["schemas"]["app__api__assistant__ConversationSummary"];

export type ChatError = "ai_not_configured" | "ai_busy" | "ai_unavailable" | "ai_limit_reached" | "ai_rate_limited" | "generic";
export type ChatResult = { conversation?: Conversation; error?: ChatError };

const KNOWN: readonly string[] = ["ai_not_configured", "ai_busy", "ai_unavailable", "ai_limit_reached", "ai_rate_limited"];

function errorOf(error: unknown): ChatError {
  const detail = error instanceof ApiError ? (error.body as { detail?: unknown } | null)?.detail : null;
  return typeof detail === "string" && KNOWN.includes(detail) ? (detail as ChatError) : "generic";
}

/** A new chat with an agent, optionally narrowed to some branches and carrying over the last exchange of another chat. */
export async function startConversation(input: {
  agentKey: string;
  locationIds: string[] | null;
  handoffFrom?: string | null;
  pageContext?: string | null;
}): Promise<ChatResult> {
  const { api, scope } = await getTenant();
  try {
    const conversation = unwrap(
      await api.POST("/ai/conversations", {
        params: scope,
        body: {
          agent_key: input.agentKey,
          location_ids: input.locationIds,
          handoff_from: input.handoffFrom ?? null,
          page_context: input.pageContext ?? null,
        },
      }),
    );
    return { conversation };
  } catch (error) {
    return { error: errorOf(error) };
  }
}

export async function sendMessage(conversationId: string, text: string): Promise<ChatResult> {
  const question = text.trim();
  if (!question) return {};
  const { api, scope } = await getTenant();
  try {
    const conversation = unwrap(
      await api.POST("/ai/conversations/{conversation_id}/messages", {
        params: { ...scope, path: { conversation_id: conversationId } },
        body: { text: question },
      }),
    );
    return { conversation };
  } catch (error) {
    return { error: errorOf(error) };
  }
}

export async function openConversation(conversationId: string): Promise<ChatResult> {
  const { api, scope } = await getTenant();
  const { data } = await api.GET("/ai/conversations/{conversation_id}", { params: { ...scope, path: { conversation_id: conversationId } } });
  return data ? { conversation: data } : { error: "generic" };
}

export async function agentConversations(agentKey: string): Promise<ConversationSummary[]> {
  const { api, scope } = await getTenant();
  const { data } = await api.GET("/ai/conversations", { params: { ...scope, query: { agent: agentKey } } });
  return data ?? [];
}

/** Confirm or decline a card the agent prepared; the chat comes back with the card's final state. */
export async function decideAction(conversationId: string, actionId: string, decision: "confirm" | "reject"): Promise<ChatResult> {
  const { api, scope } = await getTenant();
  const params = { ...scope, path: { action_id: actionId } };
  try {
    if (decision === "confirm") unwrap(await api.POST("/ai/pending-actions/{action_id}/confirm", { params }));
    else unwrap(await api.POST("/ai/pending-actions/{action_id}/reject", { params }));
  } catch {
    // The card shows the action's final state (expired, failed) after the reload.
  }
  revalidatePath("/schedule");
  return openConversation(conversationId);
}
