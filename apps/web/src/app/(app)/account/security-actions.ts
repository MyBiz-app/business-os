"use server";

import { BRAND } from "@business-os/i18n/brand";
import { revalidatePath } from "next/cache";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";

import { API_URL } from "@/lib/api";
import { DEVICE_COOKIE, deviceLabel, isCode } from "@/lib/mfa";
import { createClient } from "@/lib/supabase/server";

export type EnrollState = { error?: string; factorId?: string; qr?: string; secret?: string; done?: boolean };

/** Step one of turning on two-step sign-in: a new authenticator and the QR code to scan. */
export async function startEnrollment(_state: EnrollState): Promise<EnrollState> {
  const supabase = await createClient();
  // A scan that was never confirmed would otherwise pile up.
  const { data: factors } = await supabase.auth.mfa.listFactors();
  for (const stale of factors?.all.filter((f) => f.status === "unverified") ?? []) {
    await supabase.auth.mfa.unenroll({ factorId: stale.id });
  }
  const { data, error } = await supabase.auth.mfa.enroll({
    factorType: "totp",
    friendlyName: `${BRAND.name} ${new Date().toISOString().slice(0, 16)}`,
  });
  if (error || !data) return { error: "generic" };
  return { factorId: data.id, qr: data.totp.qr_code, secret: data.totp.secret };
}

/** Step two: the first code proves the app is set up; from then on the session is "two-step". */
export async function confirmEnrollment(state: EnrollState, formData: FormData): Promise<EnrollState> {
  const code = String(formData.get("code") ?? "").trim();
  const factorId = String(formData.get("factor") ?? "");
  if (!isCode(code)) return { ...state, error: "invalid_code" };
  const { error } = await (await createClient()).auth.mfa.challengeAndVerify({ factorId, code });
  if (error) return { ...state, error: "invalid_code" };
  await reportSecurityEvent("mfa_enabled");
  revalidatePath("/account");
  return { done: true };
}

export type RemoveState = { error?: string; done?: boolean };

/** Turning it off needs a session that already entered a code. */
export async function removeFactor(_state: RemoveState, formData: FormData): Promise<RemoveState> {
  const { error } = await (await createClient()).auth.mfa.unenroll({ factorId: String(formData.get("factor") ?? "") });
  if (error) return { error: error.code === "insufficient_aal" ? "needs_recent_code" : "generic" };
  await reportSecurityEvent("mfa_disabled");
  revalidatePath("/account");
  return { done: true };
}

/** Lets the businesses the person works for see in their audit log that two-step sign-in was
 * turned on or off. Never blocks the page. */
async function reportSecurityEvent(kind: "mfa_enabled" | "mfa_disabled"): Promise<void> {
  try {
    const { data } = await (await createClient()).auth.getSession();
    if (!data.session) return;
    await fetch(`${API_URL}/me/devices/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${data.session.access_token}` },
      body: JSON.stringify({ kind }),
      cache: "no-store",
    });
  } catch {
    // the audit entry is a convenience; turning two-step on or off has already worked
  }
}

/** Ends every session of the account on every device, this one included. */
export async function signOutEverywhere(): Promise<void> {
  await (await createClient()).auth.signOut({ scope: "global" });
  redirect("/login");
}

/** Tells the API which browser this is, once per browser session. The API emails the person when
 * it is a device the account has not signed in from before. Never blocks the page. */
export async function registerDevice(locale: string): Promise<void> {
  try {
    const jar = await cookies();
    let id = jar.get(DEVICE_COOKIE)?.value;
    if (!id) {
      id = crypto.randomUUID() + crypto.randomUUID();
      jar.set(DEVICE_COOKIE, id, { path: "/", httpOnly: true, sameSite: "lax", maxAge: 60 * 60 * 24 * 730, secure: process.env.NODE_ENV === "production" });
    }
    const supabase = await createClient();
    const { data } = await supabase.auth.getSession();
    if (!data.session) return;
    await fetch(`${API_URL}/me/devices/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${data.session.access_token}` },
      body: JSON.stringify({ device_id: id, label: deviceLabel((await headers()).get("user-agent") ?? ""), locale: locale === "en" ? "en" : "he" }),
      cache: "no-store",
    });
  } catch {
    // a failed check must never get in the way of the person's work
  }
}
