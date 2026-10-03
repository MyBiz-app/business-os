import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { SignupForm } from "./signup-form";

export default async function SignupPage() {
  const t = await getTranslations("auth");

  return (
    <>
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">{t("signup.title")}</h1>
        <p className="text-sm text-muted">{t("signup.subtitle")}</p>
      </div>
      <SignupForm />
      <p className="text-sm text-muted">
        {t("signup.haveAccount")}{" "}
        <Link href="/login" className="text-primary underline-offset-4 hover:underline">
          {t("signup.loginLink")}
        </Link>
      </p>
    </>
  );
}
