import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { LoginForm } from "./login-form";

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const t = await getTranslations("auth");
  const { error } = await searchParams;

  return (
    <>
      <h1 className="text-2xl font-bold">{t("login.title")}</h1>
      <LoginForm initialError={error === "link_invalid" ? "link_invalid" : undefined} />
      <p className="text-sm text-muted">
        {t("login.noAccount")}{" "}
        <Link href="/signup" className="text-primary underline-offset-4 hover:underline">
          {t("login.signupLink")}
        </Link>
      </p>
    </>
  );
}
