"use server";

import { API_URL } from "@/lib/api";

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
