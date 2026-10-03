import type { EmailOtpType } from "@supabase/supabase-js";
import { type NextRequest, NextResponse } from "next/server";

import { createClient } from "@/lib/supabase/server";

const OTP_TYPES = new Set<EmailOtpType>(["email", "signup", "recovery", "email_change", "invite"]);

/** Target of the links in confirmation and password-reset emails. */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const next = searchParams.get("next");
  // Only same-site paths, never an absolute URL from the query string.
  const destination = next?.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";

  if (tokenHash && type && OTP_TYPES.has(type)) {
    const supabase = await createClient();
    const { error } = await supabase.auth.verifyOtp({ type, token_hash: tokenHash });
    if (!error) return NextResponse.redirect(new URL(destination, request.url));
  }

  return NextResponse.redirect(new URL("/login?error=link_invalid", request.url));
}
