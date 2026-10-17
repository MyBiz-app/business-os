import { ShieldAlert } from "lucide-react";
import { getFormatter, getTranslations } from "next-intl/server";
import Link from "next/link";

import { getApi } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";

/** Reminds owners and managers (and the MyBiz team) without an authenticator to turn on
 * two-step sign-in, with the day it becomes required. Shows nothing for everyone else. */
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
  const text =
    platform || policy.mfa_required_now
      ? t(platform ? "mfa.requiredTeam" : "mfa.requiredBusiness")
      : t("mfa.requiredSoon", { date: (await getFormatter()).dateTime(new Date(policy.mfa_required_from ?? ""), { dateStyle: "medium", timeZone: "UTC" }) });
  return (
    <div role="status" className="flex flex-wrap items-center justify-center gap-3 border-b border-border bg-warning/10 px-4 py-2 text-sm">
      <ShieldAlert aria-hidden="true" className="size-4" />
      <span>{text}</span>
      <Link href="/account#security" className="font-medium underline underline-offset-4">
        {t("mfa.enable")}
      </Link>
    </div>
  );
}
