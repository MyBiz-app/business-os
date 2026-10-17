import type { MetadataRoute } from "next";

import { siteOrigin } from "@/lib/origin";
import { indexingAllowed } from "@/lib/site-config";

/** Search engines may index the marketing site of the production deployment only (not the business
 * app, and nothing at all on staging or previews). */
export default async function robots(): Promise<MetadataRoute.Robots> {
  if (!indexingAllowed()) return { rules: { userAgent: "*", disallow: "/" } };
  const origin = await siteOrigin();
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/dashboard", "/platform", "/start/finish", "/auth/", "/invite/"] },
    sitemap: `${origin}/sitemap.xml`,
  };
}
