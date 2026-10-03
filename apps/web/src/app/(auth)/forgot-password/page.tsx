import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { ForgotForm } from "./forgot-form";

export default async function ForgotPasswordPage() {
  const t = await getTranslations("auth.forgot");

  return (
    <>
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <p className="text-sm text-muted">{t("body")}</p>
      </div>
      <ForgotForm />
      <Link href="/login" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("backToLogin")}
      </Link>
    </>
  );
}
