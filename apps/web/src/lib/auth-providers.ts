import "server-only";

import { availableChannels, type OtpChannel } from "@/lib/otp";
import { supabaseConfig } from "@/lib/supabase/env";

/** Sign-in providers offered next to email and password, in the order shown. */
export const OAUTH_PROVIDERS = ["google", "apple"] as const;
export type OAuthProvider = (typeof OAUTH_PROVIDERS)[number];

/** Apple needs a paid developer account, so its button stays a "coming soon" placeholder until
 * AUTH_APPLE_ENABLED=true is set (after Apple is switched on in Supabase). */
export const appleEnabled = () => process.env.AUTH_APPLE_ENABLED === "true";

/** A button on the sign-in screens; `live` false renders it disabled with a "coming soon" badge. */
export type ProviderButton = { provider: OAuthProvider; live: boolean };

/** The buttons to show, in order. Google appears once it is switched on in Supabase
 * (Authentication → Sign In / Providers), since a button for one that is off would only lead to
 * an error page. Apple is always shown, live only when the flag and Supabase both allow it. */
async function authSettings(): Promise<{ external?: Record<string, boolean> } | null> {
  try {
    const { url, key } = supabaseConfig();
    const response = await fetch(`${url}/auth/v1/settings`, { headers: { apikey: key }, next: { revalidate: 300 } });
    if (response.ok) return (await response.json()) as { external?: Record<string, boolean> };
  } catch {
    // Settings unreachable: nothing beyond the defaults.
  }
  return null;
}

/** WhatsApp codes go through the same SMS provider; AUTH_WHATSAPP_ENABLED=true shows the option
 * once the provider's WhatsApp sender is approved. */
export const whatsappEnabled = () => process.env.AUTH_WHATSAPP_ENABLED === "true";

/** The ways to get a one-time sign-in code: email always, phone once the project has an SMS provider. */
export async function codeChannels(): Promise<OtpChannel[]> {
  return availableChannels(await authSettings(), whatsappEnabled());
}

export async function providerButtons(): Promise<ProviderButton[]> {
  const external = (await authSettings())?.external ?? {};
  const buttons: ProviderButton[] = [];
  if (external.google) buttons.push({ provider: "google", live: true });
  buttons.push({ provider: "apple", live: appleEnabled() && Boolean(external.apple) });
  return buttons;
}
