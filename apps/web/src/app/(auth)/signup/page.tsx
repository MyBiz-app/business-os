import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { OAuthButtons } from "@/components/auth/oauth-buttons";
import { safeNext } from "@/lib/navigation";

import { SignupForm } from "./signup-form";

export default async function SignupPage({ searchParams }: PageProps<"/signup">) {
  const t = await getTranslations("auth");
  const nextPath = safeNext((await searchParams).next) ?? undefined;

  return (
    <>
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">{t("signup.title")}</h1>
        <p className="text-sm text-muted">{t("signup.subtitle")}</p>
      </div>
      <OAuthButtons next={nextPath} />
      <SignupForm next={nextPath} />
      <p className="text-sm text-muted">
        {t("signup.haveAccount")}{" "}
        <Link href={nextPath ? `/login?next=${encodeURIComponent(nextPath)}` : "/login"} className="text-primary underline-offset-4 hover:underline">
          {t("signup.loginLink")}
        </Link>
      </p>
    </>
  );
}
