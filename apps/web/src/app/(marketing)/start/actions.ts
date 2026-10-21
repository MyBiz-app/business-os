"use server";

import { API_URL, getApi } from "@/lib/api";

const EVENTS = ["signup_started", "signup_step"] as const;
const STEPS = ["account", "industry", "business", "base", "extras", "services", "summary"] as const;

/** Tells MyBiz which step of the sign-up a visitor reached (go-live GL21), so the console shows
 * where people drop out. Only a random visit id, the event and the step: no personal data.
 * Never throws: a lost beacon must not get in the way of signing up. */
export async function reportSignupStep(visitorId: string, event: (typeof EVENTS)[number], step?: (typeof STEPS)[number]): Promise<void> {
  if (!/^[0-9a-f-]{36}$/.test(visitorId) || !EVENTS.includes(event) || (step && !STEPS.includes(step))) return;
  await fetch(`${API_URL}/public/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ visitor_id: visitorId, event, step: step ?? null }),
  }).catch(() => null);
}

/** Whether this email already has a MyBiz account (null: could not tell, so the sign-up goes on;
 * the sign-in provider still refuses a duplicate). Used by the "website only" sign-up to send
 * people with an account to their CRM instead of opening a second business. */
export async function accountExists(email: string): Promise<boolean | null> {
  const typed = email.trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(typed) || typed.length > 254) return null;
  try {
    const api = await getApi();
    const { data } = await api.POST("/public/accounts/exists", { body: { email: typed } });
    return data ? data.exists : null;
  } catch {
    return null;
  }
}
