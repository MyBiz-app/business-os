import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { AuthHeading } from "@/components/auth/auth-shell";
import { OAuthButtons } from "@/components/auth/oauth-buttons";
import { safeNext } from "@/lib/navigation";

import { SignupForm } from "./signup-form";

export default async function SignupPage({ searchParams }: PageProps<"/signup">) {
  const t = await getTranslations("auth");
  const query = await searchParams;
  const nextPath = safeNext(query.next) ?? undefined;
  // The sign-up that began on /start already asked for the email.
  const email = typeof query.email === "string" && query.email.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(query.email) ? query.email : undefined;

  return (
    <>
      <AuthHeading title={t("signup.title")} subtitle={t("signup.subtitle")} />
      <OAuthButtons next={nextPath} />
      <SignupForm next={nextPath} email={email} />
      <p className="text-sm text-muted">
        {t("signup.haveAccount")}{" "}
        <Link href={nextPath ? `/login?next=${encodeURIComponent(nextPath)}` : "/login"} className="text-primary-ink underline underline-offset-4">
          {t("signup.loginLink")}
        </Link>
      </p>
    </>
  );
}
