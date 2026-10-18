import type { NextRequest } from "next/server";

import { createNonce, NONCE_HEADER, REPORTING_ENDPOINTS, strictCsp } from "@/lib/csp";
import { cspReportOnly, hstsHeader, indexingAllowed } from "@/lib/site-config";
import { updateSession } from "@/lib/supabase/proxy";

/** Pages under this path may be shown in a business's own website (see next.config.ts). */
const EMBED_PREFIX = "/embed/";

export async function proxy(request: NextRequest) {
  // A fresh nonce per request. Next.js reads it from the CSP request header and puts it on its own
  // scripts; our inline scripts read it from NONCE_HEADER (see app/layout.tsx).
  const nonce = createNonce();
  const embeddable = request.nextUrl.pathname.startsWith(EMBED_PREFIX);
  const policy = strictCsp(nonce, { dev: process.env.NODE_ENV !== "production", embeddable });
  const cspHeader = cspReportOnly() ? "Content-Security-Policy-Report-Only" : "Content-Security-Policy";
  request.headers.set(NONCE_HEADER, nonce);
  request.headers.set("x-pathname", request.nextUrl.pathname);
  request.headers.set(cspHeader, policy);

  const response = await updateSession(request);
  response.headers.set(cspHeader, policy);
  response.headers.set("Reporting-Endpoints", REPORTING_ENDPOINTS);
  const hsts = hstsHeader();
  if (hsts) response.headers.set("Strict-Transport-Security", hsts);
  // Everything except the production site stays out of search results (robots.ts says the same).
  if (!indexingAllowed()) response.headers.set("X-Robots-Tag", "noindex, nofollow");
  return response;
}

export const config = {
  // Everything except static files, images and the TikTok site-verification file (public/).
  matcher: ["/((?!_next/static|_next/image|favicon.ico|tiktok[A-Za-z0-9]+\\.txt$|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
