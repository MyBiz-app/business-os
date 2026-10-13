import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { AuthHeading } from "@/components/auth/auth-shell";
import { OAuthButtons } from "@/components/auth/oauth-buttons";
import { safeNext } from "@/lib/navigation";

import { SignupForm } from "./signup-form";

export default async function SignupPage({ searchParams }: PageProps<"/signup">) {
  const t = await getTranslations("auth");
  const nextPath = safeNext((await searchParams).next) ?? undefined;

  return (
    <>
      <AuthHeading title={t("signup.title")} subtitle={t("signup.subtitle")} />
      <OAuthButtons next={nextPath} />
      <SignupForm next={nextPath} />
      <p className="text-sm text-muted">
        {t("signup.haveAccount")}{" "}
        <Link href={nextPath ? `/login?next=${encodeURIComponent(nextPath)}` : "/login"} className="text-primary underline underline-offset-4">
          {t("signup.loginLink")}
        </Link>
      </p>
    </>
  );
}
