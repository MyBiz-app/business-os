import "server-only";

import { unstable_rethrow } from "next/navigation";
import { cache } from "react";

import { accountStatusItems, type AccountStatusItem } from "@/lib/account-status";
import { getApi } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";
import { getActiveMembership } from "@/lib/tenant";

/** What is worth completing in the signed-in person's account, once per request (the dot in the
 * header and the home page card share it). A failure here shows nothing rather than block a page. */
export const getAccountStatus = cache(async (): Promise<AccountStatusItem[]> => {
  try {
    const { me } = await getActiveMembership();
    const roles = me.memberships.map((m) => m.role);
    const asked = me.platform_admin || roles.some((role) => role === "owner" || role === "manager");
    const [level, policy] = asked
      ? await Promise.all([
          (await createClient()).auth.mfa.getAuthenticatorAssuranceLevel().then((r) => r.data),
          (await getApi()).GET("/me/security").then((r) => r.data),
        ])
      : [null, undefined];
    return accountStatusItems({
      platform: me.platform_admin,
      roles,
      mfaEnforced: Boolean(policy?.mfa_enforced),
      hasAuthenticator: level?.nextLevel === "aal2",
      riskAcknowledged: policy?.mfa_risk_acknowledged ?? false,
      snoozedUntil: policy?.mfa_reminder_snoozed_until,
      addressComplete: me.address_complete ?? false,
      addressSkipped: me.address_reminder_skipped ?? false,
      now: Date.now(),
    });
  } catch (error) {
    unstable_rethrow(error); // a redirect to sign in is not a failure
    return [];
  }
});
