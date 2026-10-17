import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { AuthHeading } from "@/components/auth/auth-shell";
import { needsCodeStep } from "@/lib/mfa";
import { safeNext } from "@/lib/navigation";
import { createClient } from "@/lib/supabase/server";

import { signOutToLogin } from "../../actions";
import { MfaForm } from "./mfa-form";

/** The second step of signing in: the code from the authenticator app. */
export default async function MfaPage({ searchParams }: PageProps<"/login/mfa">) {
  const t = await getTranslations("security");
  const { next } = await searchParams;
  const nextPath = safeNext(next) ?? undefined;
  // Nothing to enter (already done, or no authenticator): carry on.
  const { data: level } = await (await createClient()).auth.mfa.getAuthenticatorAssuranceLevel();
  if (!needsCodeStep(level?.currentLevel, level?.nextLevel)) redirect(nextPath ?? "/dashboard");

  return (
    <>
      <AuthHeading title={t("challenge.title")} subtitle={t("challenge.subtitle")} />
      <MfaForm next={nextPath} />
      <form action={signOutToLogin}>
        <button type="submit" className="btn-link text-sm">
          {t("challenge.signOut")}
        </button>
      </form>
    </>
  );
}
