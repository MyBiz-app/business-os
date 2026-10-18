"use server";

import { getTenant } from "@/lib/tenant";

import type { Agent } from "../ai/types";

/** The agents the bubble can show, whether an AI provider is set up, and how full the month's AI is
 * (the small dot on the button). Null when the team can't be read. */
export async function loadBubble(): Promise<{ agents: Agent[]; enabled: boolean; level: "ok" | "warn" | "over" } | null> {
  const { api, scope } = await getTenant();
  try {
    const [team, status, meter] = await Promise.all([api.GET("/ai/team", { params: scope }), api.GET("/ai/status", { params: scope }), api.GET("/ai/meter", { params: scope })]);
    if (!team.data || !status.data) return null;
    return { agents: team.data.agents, enabled: status.data.enabled, level: meter.data?.level ?? "ok" };
  } catch {
    return null;
  }
}
