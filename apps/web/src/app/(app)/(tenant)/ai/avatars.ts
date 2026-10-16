// The AI team's faces (packages/brand/agents). Static imports so the bundler fingerprints and serves them.
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
import a_gallery_01 from "@business-os/brand/agents/gallery-01.webp";
import a_gallery_02 from "@business-os/brand/agents/gallery-02.webp";
import a_gallery_03 from "@business-os/brand/agents/gallery-03.webp";
import a_gallery_04 from "@business-os/brand/agents/gallery-04.webp";
import a_gallery_05 from "@business-os/brand/agents/gallery-05.webp";
import a_gallery_06 from "@business-os/brand/agents/gallery-06.webp";
import a_gallery_07 from "@business-os/brand/agents/gallery-07.webp";
import a_gallery_08 from "@business-os/brand/agents/gallery-08.webp";
import a_gallery_09 from "@business-os/brand/agents/gallery-09.webp";
import a_gallery_10 from "@business-os/brand/agents/gallery-10.webp";
import a_gallery_11 from "@business-os/brand/agents/gallery-11.webp";
import a_gallery_12 from "@business-os/brand/agents/gallery-12.webp";
import a_gallery_13 from "@business-os/brand/agents/gallery-13.webp";
import a_gallery_14 from "@business-os/brand/agents/gallery-14.webp";
import a_gallery_15 from "@business-os/brand/agents/gallery-15.webp";
import a_gallery_16 from "@business-os/brand/agents/gallery-16.webp";

const AVATARS: Record<string, StaticImageData> = {
  "chief": a_chief,
  "secretary": a_secretary,
  "marketing": a_marketing,
  "sales": a_sales,
  "finance": a_finance,
  "team": a_team,
  "care": a_care,
  "analyst": a_analyst,
  "creative": a_creative,
  "gallery-01": a_gallery_01,
  "gallery-02": a_gallery_02,
  "gallery-03": a_gallery_03,
  "gallery-04": a_gallery_04,
  "gallery-05": a_gallery_05,
  "gallery-06": a_gallery_06,
  "gallery-07": a_gallery_07,
  "gallery-08": a_gallery_08,
  "gallery-09": a_gallery_09,
  "gallery-10": a_gallery_10,
  "gallery-11": a_gallery_11,
  "gallery-12": a_gallery_12,
  "gallery-13": a_gallery_13,
  "gallery-14": a_gallery_14,
  "gallery-15": a_gallery_15,
  "gallery-16": a_gallery_16,
};

/** The picture for an agent: its chosen preset, else its own key (the nine defaults); null for a custom agent without one. */
export function avatarFor(preset: string | null | undefined, key: string): string | null {
  return (preset && AVATARS[preset]?.src) || AVATARS[key]?.src || null;
}
