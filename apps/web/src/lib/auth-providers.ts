import "server-only";

import { supabaseConfig } from "@/lib/supabase/env";

/** Sign-in providers offered next to email and password, in the order shown. */
export const OAUTH_PROVIDERS = ["google", "apple"] as const;
export type OAuthProvider = (typeof OAUTH_PROVIDERS)[number];

/** The providers switched on in Supabase (Authentication → Sign In / Providers). A button for
 * one that is off would only lead to an error page, so each one appears once it is set up. */
export async function enabledProviders(): Promise<OAuthProvider[]> {
  const { url, key } = supabaseConfig();
  try {
    const response = await fetch(`${url}/auth/v1/settings`, { headers: { apikey: key }, next: { revalidate: 300 } });
    if (!response.ok) return [];
    const { external } = (await response.json()) as { external?: Record<string, boolean> };
    return OAUTH_PROVIDERS.filter((provider) => external?.[provider]);
  } catch {
    return [];
  }
}
