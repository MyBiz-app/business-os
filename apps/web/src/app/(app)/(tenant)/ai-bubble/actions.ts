"use server";

import { getTenant } from "@/lib/tenant";

import type { Agent } from "../ai/types";

/** The agents the bubble can show, and whether an AI provider is set up. Null when the team can't be read. */
export async function loadBubble(): Promise<{ agents: Agent[]; enabled: boolean } | null> {
  const { api, scope } = await getTenant();
  try {
    const [team, status] = await Promise.all([api.GET("/ai/team", { params: scope }), api.GET("/ai/status", { params: scope })]);
    if (!team.data || !status.data) return null;
    return { agents: team.data.agents, enabled: status.data.enabled };
  } catch {
    return null;
  }
}
