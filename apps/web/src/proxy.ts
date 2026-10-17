import type { NextRequest } from "next/server";

import { createNonce, NONCE_HEADER, REPORTING_ENDPOINTS, strictCsp } from "@/lib/csp";
import { updateSession } from "@/lib/supabase/proxy";

export async function proxy(request: NextRequest) {
  // A fresh nonce per request. Next.js reads it from the CSP request header and puts it on its own
  // scripts; our inline scripts read it from NONCE_HEADER (see app/layout.tsx).
  const nonce = createNonce();
  const policy = strictCsp(nonce, { dev: process.env.NODE_ENV !== "production" });
  request.headers.set(NONCE_HEADER, nonce);
  request.headers.set("x-pathname", request.nextUrl.pathname);
  request.headers.set("content-security-policy-report-only", policy);

  const response = await updateSession(request);
  response.headers.set("Content-Security-Policy-Report-Only", policy);
  response.headers.set("Reporting-Endpoints", REPORTING_ENDPOINTS);
  return response;
}

export const config = {
  // Everything except static files, images and the TikTok site-verification file (public/).
  matcher: ["/((?!_next/static|_next/image|favicon.ico|tiktok[A-Za-z0-9]+\\.txt$|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
