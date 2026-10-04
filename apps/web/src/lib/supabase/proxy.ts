import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";

import { safeNext } from "@/lib/navigation";

import { supabaseConfig } from "./env";

const PUBLIC_PAGES = new Set(["/", "/login", "/signup", "/check-email", "/forgot-password"]);
const AUTH_PAGES = new Set(["/", "/login", "/signup"]);

// The marketing site and the public pages around sign-in and joining.
const PUBLIC_PREFIXES = ["/auth/", "/invite/", "/join/", "/features", "/industries/", "/pricing", "/about", "/contact", "/legal/"];

function isPublic(pathname: string) {
  return PUBLIC_PAGES.has(pathname) || PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
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

  if (!signedIn && !isPublic(pathname)) return redirectTo("/login");
  if (signedIn && AUTH_PAGES.has(pathname)) {
    return redirectTo(safeNext(request.nextUrl.searchParams.get("next")) ?? "/dashboard");
  }

  return response;
}
