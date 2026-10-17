import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";

import { CSP_REPORT_PATH } from "@/lib/csp";
import { ACTIVITY_COOKIE, isInactive, MFA_PAGE, needsCodeStep } from "@/lib/mfa";
import { safeNext } from "@/lib/navigation";

import { supabaseConfig } from "./env";

const PUBLIC_PAGES = new Set(["/", "/login", "/login/code", "/signup", "/check-email", "/email-confirmed", "/forgot-password", "/start", "/getting-started", "/sitemap.xml", "/robots.txt", CSP_REPORT_PATH]);
const PUBLIC_ASSETS = ["/opengraph-image", "/twitter-image"];
const AUTH_PAGES = new Set(["/", "/login", "/login/code", "/signup"]);

// The marketing site and the public pages around sign-in and joining.
const PUBLIC_PREFIXES = ["/auth/", "/invite/", "/join/", "/inquiry/", "/q/", "/features", "/industries", "/pricing", "/about", "/contact", "/legal/"];

function isPublic(pathname: string) {
  return PUBLIC_PAGES.has(pathname) || [...PUBLIC_PREFIXES, ...PUBLIC_ASSETS].some((prefix) => pathname.startsWith(prefix));
}

/** Refreshes the session cookie and redirects based on whether the user is signed in. */
export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });
  const { url, key } = supabaseConfig();

  const supabase = createServerClient(url, key, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (cookiesToSet) => {
        for (const { name, value } of cookiesToSet) request.cookies.set(name, value);
        response = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) {
          response.cookies.set(name, value, options);
        }
      },
    },
  });

  // Validates the token (signature and expiry) rather than trusting the cookie.
  const { data } = await supabase.auth.getClaims();
  const signedIn = Boolean(data?.claims);
  const { pathname } = request.nextUrl;

  const redirectTo = (path: string) => {
    const target = new URL(path, request.url);
    const redirect = NextResponse.redirect(target);
    for (const cookie of response.cookies.getAll()) redirect.cookies.set(cookie);
    return redirect;
  };

  // Idle for too long: sign out. The browser refreshes the stamp on every click and key press;
  // background refreshes of the page don't count.
  const stamp = request.cookies.get(ACTIVITY_COOKIE)?.value;
  if (signedIn && isInactive(stamp, Date.now())) {
    await supabase.auth.signOut();
    const expired = redirectTo("/login?error=session_expired");
    expired.cookies.delete(ACTIVITY_COOKIE);
    return expired;
  }
  if (signedIn && !stamp) {
    response.cookies.set(ACTIVITY_COOKIE, String(Date.now()), { path: "/", sameSite: "lax", maxAge: 60 * 60 * 24 * 30, secure: process.env.NODE_ENV === "production" });
  } else if (!signedIn && stamp) {
    response.cookies.delete(ACTIVITY_COOKIE);
  }

  // Someone with an authenticator must enter a code before anything else (the API refuses the
  // sensitive requests of a session without one anyway).
  if (signedIn && data?.claims?.aal !== "aal2" && !isPublic(pathname) && pathname !== MFA_PAGE && !pathname.startsWith("/api/")) {
    const { data: level } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
    if (needsCodeStep(level?.currentLevel, level?.nextLevel)) {
      const back = pathname === "/dashboard" ? "" : `?next=${encodeURIComponent(pathname + request.nextUrl.search)}`;
      return redirectTo(`${MFA_PAGE}${back}`);
    }
  }

  if (!signedIn && !isPublic(pathname)) {
    // Come back here after signing in (e.g. the payment step of the sign-up journey).
    const back = pathname === "/" || pathname === "/dashboard" ? "" : `?next=${encodeURIComponent(pathname + request.nextUrl.search)}`;
    return redirectTo(`/login${back}`);
  }
  if (signedIn && AUTH_PAGES.has(pathname)) {
    return redirectTo(safeNext(request.nextUrl.searchParams.get("next")) ?? "/dashboard");
  }

  return response;
}
