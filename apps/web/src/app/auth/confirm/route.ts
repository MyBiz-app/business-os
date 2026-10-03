import type { EmailOtpType } from "@supabase/supabase-js";
import { type NextRequest, NextResponse } from "next/server";

import { AUTH_NEXT_COOKIE, safeNext } from "@/lib/navigation";
import { createClient } from "@/lib/supabase/server";

const OTP_TYPES = new Set<EmailOtpType>(["email", "signup", "recovery", "email_change", "invite"]);

/**
 * Target of the links in confirmation and password-reset emails. Accepts both our own
 * templates (`token_hash` + `type`, works from any browser) and Supabase's default templates
 * (`code`, works in the browser that started the flow).
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const code = searchParams.get("code");
  // Only same-site paths. Sign-up stores its destination in a cookie, because the email
  // template's link does not carry it.
  const destination =
    safeNext(searchParams.get("next")) ??
    safeNext(request.cookies.get(AUTH_NEXT_COOKIE)?.value) ??
    "/dashboard";

  const supabase = await createClient();
  let verified = false;
  if (tokenHash && type && OTP_TYPES.has(type)) {
    verified = !(await supabase.auth.verifyOtp({ type, token_hash: tokenHash })).error;
  } else if (code) {
    verified = !(await supabase.auth.exchangeCodeForSession(code)).error;
  }

  const target = verified ? destination : "/login?error=link_invalid";
  const response = NextResponse.redirect(new URL(target, request.url));
  if (verified) response.cookies.delete(AUTH_NEXT_COOKIE);
  return response;
}
