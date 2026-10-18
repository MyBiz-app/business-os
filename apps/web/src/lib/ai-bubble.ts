// Which AI agent the floating bubble shows on which screen. The screen map lives on the server
// (each agent card carries its `routes`), so there is one source for the bubble and the API.

type Routed = { key: string; routes?: readonly string[] };

/** Screens that already are the AI team (or hand over to it): the bubble stays out of the way. */
const HIDDEN = ["/ai", "/assistant", "/upgrade"];

const FAN_SIZE = 5;

const under = (path: string, prefix: string) => path === prefix || path.startsWith(`${prefix}/`);

export function bubbleHidden(path: string): boolean {
  return HIDDEN.some((prefix) => under(path, prefix));
}

/** The agent that suits a screen (the longest matching route wins); the chief everywhere else. */
export function agentForPath(path: string, agents: readonly Routed[]): string {
  let best: { key: string; length: number } | null = null;
  for (const agent of agents)
    for (const route of agent.routes ?? [])
      if (under(path, route) && (!best || route.length > best.length)) best = { key: agent.key, length: route.length };
  return best?.key ?? "chief";
}

/**
 * The agents offered in the fan. The agent already on the round button is never offered again;
 * the rest follow by relevance: the screen's agent, the chief, then the others in team order.
 */
export function fanFor(path: string, agents: readonly Routed[], shownKey: string): string[] {
  const keys = agents.map((a) => a.key);
  const wanted = [agentForPath(path, agents), "chief", ...keys];
  const picked: string[] = [];
  for (const key of wanted) if (key !== shownKey && keys.includes(key) && !picked.includes(key)) picked.push(key);
  return picked.slice(0, FAN_SIZE);
}
