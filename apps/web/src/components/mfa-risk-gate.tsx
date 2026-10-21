"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { MfaRiskDialog } from "@/components/mfa-risk-dialog";
import { withoutRiskPrompt } from "@/lib/account-status";

/** A sensitive action refused for an owner or manager who has neither a code nor the confirmed
 * warning comes back to the same page with `mfa=ack` (see `sendToTwoStepSetup` in lib/api.ts): the
 * warning opens right there, instead of a detour to the account page. After confirming, the page
 * reloads and the person repeats the action; cancelling goes back to where they were. */
export function MfaRiskGate() {
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  if (params.get("mfa") !== "ack") return null;
  const clean = withoutRiskPrompt(pathname, params.toString());
  return (
    <MfaRiskDialog
      source="sensitive_action"
      onDone={() => {
        router.replace(clean, { scroll: false });
        router.refresh();
      }}
      onClose={() => {
        // The refused page itself would only be refused again: step back to the previous one.
        if (window.history.length > 1) router.back();
        else router.replace("/");
      }}
    />
  );
}
