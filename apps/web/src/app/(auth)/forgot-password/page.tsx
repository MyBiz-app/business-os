import { KeyRound } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { AuthHeading } from "@/components/auth/auth-shell";

import { ForgotForm } from "./forgot-form";

export default async function ForgotPasswordPage() {
  const t = await getTranslations("auth.forgot");

  return (
    <>
      <AuthHeading title={t("title")} subtitle={t("body")} icon={<KeyRound className="size-6" />} />
      <ForgotForm />
      <Link href="/login" className="text-sm text-primary-ink underline-offset-4 hover:underline">
        {t("backToLogin")}
      </Link>
    </>
  );
}
