"use server";

import type { AuthError } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { appleEnabled, OAUTH_PROVIDERS, type OAuthProvider, whatsappEnabled } from "@/lib/auth-providers";
import { AUTH_NEXT_COOKIE, safeNext } from "@/lib/navigation";
import { OTP_LENGTH, type OtpChannel, toE164 } from "@/lib/otp";
import { siteOrigin } from "@/lib/origin";
import { resumeMetadata } from "@/lib/resume";
import { createClient } from "@/lib/supabase/server";

export type FormState = { error?: string; notice?: string; email?: string };

/** State of the one-time-code sign-in: after the code is sent `target` is the email or E.164 number. */
export type CodeState = { error?: string; channel?: OtpChannel; target?: string };

const KNOWN_ERRORS = new Set([
  "invalid_credentials",
  "email_not_confirmed",
  "weak_password",
  "user_already_exists",
  "over_email_send_rate_limit",
  "email_send_failed",
  "over_sms_send_rate_limit",
]);

/** Maps a Supabase auth error to a translation key under `auth.errors`. */
function errorKey(error: AuthError): string {
  // The email could not be sent (e.g. no email provider yet: Supabase's built-in one only
  // sends to the project's team), so the account was not created.
  if (error.code === "email_address_not_authorized" || /sending.*email/i.test(error.message)) return "email_send_failed";
  return error.code && KNOWN_ERRORS.has(error.code) ? error.code : "generic";
}

function field(formData: FormData, name: string): string {
  return String(formData.get(name) ?? "").trim();
}

export async function login(_state: FormState, formData: FormData): Promise<FormState> {
  const email = field(formData, "email");
  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({
    email,
    password: String(formData.get("password") ?? ""),
  });
  if (error) return { error: errorKey(error), email };
  redirect(safeNext(formData.get("next")) ?? "/dashboard");
}

/** Google or Apple: off to the provider, back through /auth/confirm, then on to `next`. */
export async function oauthSignIn(formData: FormData): Promise<void> {
  const provider = String(formData.get("provider") ?? "") as OAuthProvider;
  if (!OAUTH_PROVIDERS.includes(provider)) redirect("/login");
  if (provider === "apple" && !appleEnabled()) redirect("/login");
  const next = safeNext(formData.get("next"));
  // The return trip is in this same browser, so the destination can wait in a cookie (the
  // redirect address stays fixed, as Supabase's allow list wants).
  if (next) {
    (await cookies()).set(AUTH_NEXT_COOKIE, next, { path: "/", maxAge: 60 * 60, httpOnly: true, sameSite: "lax" });
  }
  const supabase = await createClient();
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider,
    options: { redirectTo: `${await siteOrigin()}/auth/confirm` },
  });
  redirect(error || !data.url ? "/login?error=link_invalid" : data.url);
}

export async function signup(_state: FormState, formData: FormData): Promise<FormState> {
  const email = field(formData, "email");
  const supabase = await createClient();
  const next = safeNext(formData.get("next"));
  const { data, error } = await supabase.auth.signUp({
    email,
    password: String(formData.get("password") ?? ""),
    options: { emailRedirectTo: `${await siteOrigin()}/auth/confirm`, data: resumeMetadata(next) },
  });
  if (error) return { error: errorKey(error), email };
  // Email confirmation turned off (e.g. on staging, before an email provider): signed in now.
  if (data.session) redirect(next ?? "/dashboard");
  // Where to go after the email link is confirmed (e.g. back to an invitation).
  if (next) {
    (await cookies()).set(AUTH_NEXT_COOKIE, next, { path: "/", maxAge: 60 * 60 * 24, httpOnly: true, sameSite: "lax" });
  }
  redirect(`/check-email?email=${encodeURIComponent(email)}`);
}

export async function requestPasswordReset(
  _state: FormState,
  formData: FormData,
): Promise<FormState> {
  const email = field(formData, "email");
  const supabase = await createClient();
  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${await siteOrigin()}/auth/confirm?next=/reset-password`,
  });
  // The same message whether or not the account exists, so emails cannot be probed.
  if (error && error.code === "over_email_send_rate_limit") return { error: errorKey(error), email };
  return { notice: "sent", email };
}

export async function updatePassword(_state: FormState, formData: FormData): Promise<FormState> {
  const supabase = await createClient();
  const { error } = await supabase.auth.updateUser({
    password: String(formData.get("password") ?? ""),
  });
  if (error) return { error: errorKey(error) };
  redirect("/dashboard");
}

/** Signs out on purpose and lands on the marketing home page with a confirmation. An expired or
 * revoked session is different: the proxy sends it to /login with `next` to come back. */
export async function signOut(): Promise<void> {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/?signed_out=1");
}

/** Signs out to sign in again as someone else (wrong invited email, closed business). */
export async function signOutToLogin(): Promise<void> {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Step one of signing in with a code: email (new people are signed up) or, for someone who
 * verified a number on their account, SMS or WhatsApp. */
export async function sendLoginCode(_state: CodeState, formData: FormData): Promise<CodeState> {
  const channel = field(formData, "channel") as OtpChannel;
  const supabase = await createClient();
  if (channel === "email") {
    const email = field(formData, "email").toLowerCase();
    if (!EMAIL.test(email)) return { error: "invalid_email" };
    const { error } = await supabase.auth.signInWithOtp({ email, options: { shouldCreateUser: true } });
    if (error) return { error: errorKey(error) };
    return { channel, target: email };
  }
  if (channel !== "sms" && (channel !== "whatsapp" || !whatsappEnabled())) return { error: "generic" };
  const phone = toE164(field(formData, "phone"));
  if (!phone) return { error: "invalid_phone" };
  const { error } = await supabase.auth.signInWithOtp({ phone, options: { shouldCreateUser: false, channel } });
  if (error) return { error: error.code === "otp_disabled" || error.code === "user_not_found" ? "unknown_phone" : errorKey(error) };
  return { channel, target: phone };
}

/** Step two: the six digits. */
export async function verifyLoginCode(_state: CodeState, formData: FormData): Promise<CodeState> {
  const channel = field(formData, "channel") as OtpChannel;
  const target = field(formData, "target");
  const token = field(formData, "code");
  if (!new RegExp(`^\\d{${OTP_LENGTH}}$`).test(token)) return { error: "invalid_code", channel, target };
  const supabase = await createClient();
  const { error } = await supabase.auth.verifyOtp(
    channel === "email" ? { email: target, token, type: "email" } : { phone: target, token, type: "sms" },
  );
  if (error) return { error: "invalid_code", channel, target };
  redirect(safeNext(formData.get("next")) ?? "/dashboard");
}
