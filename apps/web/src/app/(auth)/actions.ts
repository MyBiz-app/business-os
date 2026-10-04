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
]);

/** Maps a Supabase auth error to a translation key under `auth.errors`. */
function errorKey(error: AuthError): string {
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
  const { error } = await supabase.auth.signUp({
    email,
    password: String(formData.get("password") ?? ""),
    options: { emailRedirectTo: `${await siteOrigin()}/auth/confirm` },
  });
  if (error) return { error: errorKey(error), email };
  // Where to go after the email link is confirmed (e.g. back to an invitation).
  const next = safeNext(formData.get("next"));
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
