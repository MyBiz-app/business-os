// Which AI agent suits which screen of the business app, and small helpers for the agent list.

const TAB_AGENTS: Record<string, string> = {
  today: "secretary",
  clients: "marketing",
  inbox: "marketing",
  numbers: "analyst",
};

/** The agent the floating button opens on a tab; the chief everywhere else. */
export function agentForTab(tab: string | undefined): string {
  return (tab && TAB_AGENTS[tab]) || "chief";
}

type Pickable = { key: string; state: string };

/** The agent to open: the wanted one if it can be talked to, else the chief, else the first usable. */
export function pickAgent<T extends Pickable>(agents: readonly T[], wanted: string | undefined): T | undefined {
  const usable = agents.filter((agent) => agent.state === "active");
  return usable.find((agent) => agent.key === wanted) ?? usable.find((agent) => agent.key === "chief") ?? usable[0];
}

/** The first letter of a name, for an agent without a picture. */
export function initialOf(name: string): string {
  return Array.from(name.trim())[0] ?? "?";
}
