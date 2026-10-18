/** The chief of staff, who sits at the top of the team. */
export const CHIEF = "chief";

/** The eight specialists under the chief, in the order they appear on the landing pages. */
export const SPECIALISTS = ["secretary", "marketing", "sales", "finance", "team", "care", "analyst", "creative"] as const;

export type TeamKey = typeof CHIEF | (typeof SPECIALISTS)[number];

/** The specialist a product or industry page introduces ("your agent for this field"). */
const INDUSTRY_AGENT: Record<string, (typeof SPECIALISTS)[number]> = {
  home_services: "sales",
  professional: "sales",
  automotive: "sales",
  food: "care",
  events: "creative",
};

export function agentForIndustry(category: string): (typeof SPECIALISTS)[number] {
  return INDUSTRY_AGENT[category] ?? "secretary";
}
