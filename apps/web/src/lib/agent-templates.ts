export type Tone = "friendly" | "formal" | "short";

/** Every tool domain a custom agent can be given (routing, the hand-over tool, is the chief's alone). */
export const TOOL_DOMAINS = ["schedule", "bookings", "clients", "messages", "leads", "sources", "sales", "plans", "quotes", "metrics", "billing", "receipts", "balances", "shifts", "staff", "time", "inbox", "reviews", "reports", "content", "social"] as const;

/** The built-in roles an agent can be opened to; the business's own roles are added by id. */
export const SYSTEM_ROLES = ["owner", "manager", "branch_manager", "front_desk", "staff"] as const;

/** Starting points for step one of the wizard: what the agent is for, with the toolbox and tone that usually fit. The words come from the `aiTeam.wizard.templates` messages. */
export const TEMPLATES = [
  { key: "nutrition", domains: ["clients", "bookings", "messages"], tone: "friendly", color: "#16A34A" },
  { key: "purchasing", domains: ["sales", "receipts", "balances", "reports"], tone: "formal", color: "#F59E0B" },
  { key: "social", domains: ["content", "social", "leads", "messages"], tone: "friendly", color: "#EC4899" },
  { key: "hiring", domains: ["staff", "shifts", "inbox"], tone: "formal", color: "#2563EB" },
  { key: "support", domains: ["clients", "inbox", "reviews", "messages"], tone: "short", color: "#06B6D4" },
  { key: "other", domains: ["clients"], tone: "friendly", color: "#7C3AED" },
] as const satisfies readonly { key: string; domains: readonly string[]; tone: Tone; color: string }[];

export const COLORS = ["#7C3AED", "#2563EB", "#06B6D4", "#16A34A", "#F59E0B", "#EF4444", "#EC4899", "#6B7280"] as const;

export const GALLERY = Array.from({ length: 16 }, (_, i) => `gallery-${String(i + 1).padStart(2, "0")}`);

export const MAX_INSTRUCTIONS = 4000;

/** The role description the wizard's three boxes add up to. Plain labeled paragraphs: the server treats the whole thing as the business's own words, below its fixed rules. */
export function composeInstructions(parts: { does: string; never: string; knowledge: string }, labels: { does: string; never: string; knowledge: string }): string {
  return (["does", "never", "knowledge"] as const)
    .filter((k) => parts[k].trim())
    .map((k) => `${labels[k]}\n${parts[k].trim()}`)
    .join("\n\n")
    .slice(0, MAX_INSTRUCTIONS);
}
