import type { components } from "@business-os/api-client";

export type Agent = components["schemas"]["AgentCard"];
export type Team = components["schemas"]["app__api__ai_team__Team"];

/** A module that unlocks agents: its display name and monthly price, ready to show. */
export type Upsell = { name: string; price: string };
