import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { safeNext } from "@/lib/navigation";

import { LoginForm } from "./login-form";

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const t = await getTranslations("auth");
  const { error, next } = await searchParams;
  const nextPath = safeNext(next) ?? undefined;

  return (
    <>
      <h1 className="text-2xl font-bold">{t("login.title")}</h1>
      <LoginForm initialError={error === "link_invalid" ? "link_invalid" : undefined} next={nextPath} />
      <p className="text-sm text-muted">
        {t("login.noAccount")}{" "}
        <Link href={nextPath ? `/signup?next=${encodeURIComponent(nextPath)}` : "/signup"} className="text-primary underline-offset-4 hover:underline">
          {t("login.signupLink")}
        </Link>
      </p>
    </>
  );
}
