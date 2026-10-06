"use server";

import type { AuthError } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AUTH_NEXT_COOKIE, safeNext } from "@/lib/navigation";
import { siteOrigin } from "@/lib/origin";
import { createClient } from "@/lib/supabase/server";

export type FormState = { error?: string; notice?: string; email?: string };

const KNOWN_ERRORS = new Set([
  "invalid_credentials",
  "email_not_confirmed",
  "weak_password",
  "user_already_exists",
  "over_email_send_rate_limit",
  "email_send_failed",
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

export async function signup(_state: FormState, formData: FormData): Promise<FormState> {
  const email = field(formData, "email");
  const supabase = await createClient();
  const { data, error } = await supabase.auth.signUp({
    email,
    password: String(formData.get("password") ?? ""),
    options: { emailRedirectTo: `${await siteOrigin()}/auth/confirm` },
  });
  if (error) return { error: errorKey(error), email };
  const next = safeNext(formData.get("next"));
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

export async function signOut(): Promise<void> {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}
