import { ShieldAlert } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { acknowledgeMfaRisk } from "@/app/(app)/account/security-actions";
import { SubmitButton } from "@/components/form/submit-button";
import { getApi } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";

/** Warns owners and managers without an authenticator that two-step sign-in is off, and lets them
 * confirm they understand the risk (it is optional, but the sensitive actions wait for the
 * confirmation). The MyBiz team is told it is required. Shows nothing for everyone else. */
export async function MfaBanner({ memberships, platform }: { memberships: string[]; platform: boolean }) {
  const eligible = platform || memberships.some((role) => role === "owner" || role === "manager");
  if (!eligible) return null;
  const supabase = await createClient();
  const { data: level } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
  if (level?.nextLevel !== "aal1") return null; // already has an authenticator
  let policy;
  try {
    policy = (await (await getApi()).GET("/me/security")).data;
  } catch {
    return null;
  }
  if (!policy?.mfa_enforced) return null;
  const t = await getTranslations("security");
  const acknowledged = policy.mfa_risk_acknowledged;
  const text = platform ? t("mfa.requiredTeam") : t(acknowledged ? "mfa.warningAcknowledged" : "mfa.warning");
  return (
    <div role="status" className="flex flex-wrap items-center justify-center gap-3 border-b border-border bg-warning/10 px-4 py-2 text-sm">
      <ShieldAlert aria-hidden="true" className="size-4" />
      <span>{text}</span>
      <Link href="/account#security" className="inline-block py-2 font-medium underline underline-offset-4 md:py-0">
        {t("mfa.enable")}
      </Link>
      {!platform && !acknowledged && (
        <form action={acknowledgeMfaRisk}>
          <SubmitButton variant="secondary">{t("mfa.riskConfirm")}</SubmitButton>
        </form>
      )}
    </div>
  );
}
