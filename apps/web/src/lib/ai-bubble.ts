// Which AI agent the floating bubble shows on which screen. One file, so a new screen is one line.

const ROUTE_AGENTS: readonly (readonly [prefix: string, agent: string])[] = [
  ["/leads", "marketing"],
  ["/messages", "marketing"],
  ["/schedule", "secretary"],
  ["/events", "secretary"],
  ["/sales", "sales"],
  ["/quotes", "sales"],
  ["/bills", "finance"],
  ["/receipts", "finance"],
  ["/team", "team"],
  ["/reports", "analyst"],
  ["/dashboard", "analyst"],
];

/** Screens that already are the AI team (or hand over to it): the bubble stays out of the way. */
const HIDDEN = ["/ai", "/assistant", "/upgrade"];

/** The fan fills up with these after the chief and the agent of the screen. */
const FILL = ["secretary", "marketing", "sales", "finance"];
const FAN_SIZE = 5;

const under = (path: string, prefix: string) => path === prefix || path.startsWith(`${prefix}/`);

export function bubbleHidden(path: string): boolean {
  return HIDDEN.some((prefix) => under(path, prefix));
}

/** The agent that suits a screen; the chief everywhere else. */
export function agentForPath(path: string): string {
  return ROUTE_AGENTS.find(([prefix]) => under(path, prefix))?.[1] ?? "chief";
}

/** The agents offered in the fan: the chief, the one for this screen, then others, only those that can be talked to. */
export function fanFor(path: string, available: readonly string[]): string[] {
  const wanted = ["chief", agentForPath(path), ...FILL];
  const picked: string[] = [];
  for (const key of wanted) if (available.includes(key) && !picked.includes(key)) picked.push(key);
  return picked.slice(0, FAN_SIZE);
}
