import type { StaticImageData } from "next/image";

import a_chief from "@business-os/brand/agents/chief.webp";
import a_secretary from "@business-os/brand/agents/secretary.webp";
import a_marketing from "@business-os/brand/agents/marketing.webp";
import a_sales from "@business-os/brand/agents/sales.webp";
import a_finance from "@business-os/brand/agents/finance.webp";
import a_team from "@business-os/brand/agents/team.webp";
import a_care from "@business-os/brand/agents/care.webp";
import a_analyst from "@business-os/brand/agents/analyst.webp";
import a_creative from "@business-os/brand/agents/creative.webp";
import a_gallery_02 from "@business-os/brand/agents/gallery-02.webp";
import a_gallery_05 from "@business-os/brand/agents/gallery-05.webp";
import a_gallery_09 from "@business-os/brand/agents/gallery-09.webp";

import { CHIEF, SPECIALISTS, type TeamKey } from "./ai-team-keys";

export { CHIEF, SPECIALISTS, type TeamKey };

/** The real portraits of the nine default agents (packages/brand/agents). */
export const PORTRAITS: Record<TeamKey, StaticImageData> = {
  chief: a_chief,
  secretary: a_secretary,
  marketing: a_marketing,
  sales: a_sales,
  finance: a_finance,
  team: a_team,
  care: a_care,
  analyst: a_analyst,
  creative: a_creative,
};

/** Faces for the branch agents shown in the "network" view (a branch manager agent per branch). */
export const BRANCH_PORTRAITS = [a_gallery_02, a_gallery_05, a_gallery_09] as const;

