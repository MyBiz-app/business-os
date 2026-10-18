"use server";

import { revalidatePath } from "next/cache";

import type { components } from "@business-os/api-client";

import { ApiError, apiUpload, unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

import type { Agent, Team } from "./types";

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

export type AgentError = "agent_limit" | "unknown_tool_domain" | "unknown_role" | "unknown_branch" | "image_too_large" | "unsupported_image" | "generic";
export type AgentResult = { agent?: Agent; error?: AgentError };

const AGENT_ERRORS: readonly string[] = ["agent_limit", "unknown_tool_domain", "unknown_role", "unknown_branch"];

function agentError(error: unknown): AgentError {
  const detail = error instanceof ApiError ? (error.body as { detail?: unknown } | null)?.detail : null;
  return typeof detail === "string" && AGENT_ERRORS.includes(detail) ? (detail as AgentError) : "generic";
}

export type NewAgent = components["schemas"]["CustomAgent"];
export type AgentChange = components["schemas"]["AgentChange"];

/** The wizard's draft: a custom agent that only managers can try until it is saved into the team. */
export async function createAgentDraft(body: Omit<NewAgent, "draft" | "model_tier">): Promise<AgentResult> {
  const { api, scope } = await getTenant();
  try {
    return { agent: unwrap(await api.POST("/ai/agents", { params: scope, body: { ...body, model_tier: "fast", draft: true } })) };
  } catch (error) {
    return { error: agentError(error) };
  }
}

export async function saveAgent(agentKey: string, body: AgentChange): Promise<AgentResult> {
  const { api, scope } = await getTenant();
  try {
    const agent = unwrap(await api.PATCH("/ai/agents/{agent_key}", { params: { ...scope, path: { agent_key: agentKey } }, body }));
    revalidatePath("/ai");
    return { agent };
  } catch (error) {
    return { error: agentError(error) };
  }
}

export async function deleteAgent(agentKey: string): Promise<void> {
  const { api, scope } = await getTenant();
  await api.DELETE("/ai/agents/{agent_key}", { params: { ...scope, path: { agent_key: agentKey } } });
  revalidatePath("/ai");
}

/** An uploaded face (already cropped in the browser) for a built-in or custom agent. */
export async function uploadAgentAvatar(agentKey: string, formData: FormData): Promise<AgentResult> {
  const file = formData.get("avatar");
  if (!(file instanceof File) || file.size === 0) return { error: "unsupported_image" };
  const { tenant } = await getTenant();
  const response = await apiUpload(`/ai/agents/${encodeURIComponent(agentKey)}/avatar`, file, tenant.id);
  if (response.status === 413) return { error: "image_too_large" };
  if (response.status === 415) return { error: "unsupported_image" };
  if (!response.ok) return { error: "generic" };
  revalidatePath("/ai");
  return { agent: (await response.json()) as Agent };
}

export async function removeAgentAvatar(agentKey: string): Promise<AgentResult> {
  const { api, scope } = await getTenant();
  try {
    const agent = unwrap(await api.DELETE("/ai/agents/{agent_key}/avatar", { params: { ...scope, path: { agent_key: agentKey } } }));
    revalidatePath("/ai");
    return { agent };
  } catch (error) {
    return { error: agentError(error) };
  }
}

export type StructureResult = { team?: Team; error?: "locked_agent" | "cycle" | "generic" };

/** Saves the whole structure: reporting lines, teams and map places (owner or whoever manages the AI team). */
export async function saveStructure(body: components["schemas"]["StructureUpdate"]): Promise<StructureResult> {
  const { api, scope } = await getTenant();
  try {
    const team = unwrap(await api.PUT("/ai/structure", { params: scope, body }));
    revalidatePath("/ai");
    return { team };
  } catch (error) {
    const detail = error instanceof ApiError ? (error.body as { detail?: unknown } | null)?.detail : null;
    return { error: detail === "locked_agent" || detail === "cycle" ? detail : "generic" };
  }
}

/** The first-time guide was finished or skipped: it will not open by itself again for this person. */
export async function markAiTourSeen(): Promise<void> {
  const { api } = await getTenant();
  await api.PUT("/me/tours/{key}", { params: { path: { key: "ai_team" } } });
}
