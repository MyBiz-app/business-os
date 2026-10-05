import type { MetadataRoute } from "next";

import { siteOrigin } from "@/lib/origin";

/** Search engines may index the marketing site, not the business app. */
export default async function robots(): Promise<MetadataRoute.Robots> {
  const origin = await siteOrigin();
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/dashboard", "/platform", "/start/finish", "/auth/", "/invite/"] },
    sitemap: `${origin}/sitemap.xml`,
  };
}
