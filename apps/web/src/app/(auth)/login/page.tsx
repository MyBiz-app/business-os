import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { AuthHeading } from "@/components/auth/auth-shell";
import { OAuthButtons } from "@/components/auth/oauth-buttons";
import { safeNext } from "@/lib/navigation";

import { LoginForm } from "./login-form";

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const t = await getTranslations("auth");
  const { error, next } = await searchParams;
  const nextPath = safeNext(next) ?? undefined;

  return (
    <>
      <AuthHeading title={t("login.title")} subtitle={t("login.subtitle")} />
      <OAuthButtons next={nextPath} />
      <LoginForm initialError={error === "link_invalid" || error === "session_expired" ? error : undefined} next={nextPath} />
      <Link href={nextPath ? `/login/code?next=${encodeURIComponent(nextPath)}` : "/login/code"} className="btn-secondary px-4 py-2.5 text-center">
        {t("codeLogin.useCode")}
      </Link>
      <p className="text-sm text-muted">
        {t("login.noAccount")}{" "}
        <Link href={nextPath ? `/signup?next=${encodeURIComponent(nextPath)}` : "/signup"} className="text-primary-ink underline underline-offset-4">
          {t("login.signupLink")}
        </Link>
      </p>
    </>
  );
}
