import type { MetadataRoute } from "next";

import { siteOrigin } from "@/lib/origin";

const PAGES = [
  "/",
  "/features",
  "/pricing",
  "/start",
  "/getting-started",
  "/industries/fitness",
  "/industries/beauty",
  "/industries/clinic",
  "/industries/garage",
  "/about",
  "/contact",
  "/legal/terms",
  "/legal/privacy",
  "/legal/accessibility",
];

/** The public marketing pages, for search engines. */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = await siteOrigin();
  return PAGES.map((path) => ({
    url: `${origin}${path === "/" ? "" : path}`,
    changeFrequency: "weekly",
    priority: path === "/" ? 1 : path === "/start" || path === "/pricing" ? 0.9 : 0.6,
  }));
}
