import { LockKeyhole } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { AuthHeading } from "@/components/auth/auth-shell";

import { ResetForm } from "./reset-form";

export default async function ResetPasswordPage() {
  const t = await getTranslations("auth.reset");

  return (
    <>
      <AuthHeading title={t("title")} subtitle={t("subtitle")} icon={<LockKeyhole className="size-6" />} />
      <ResetForm />
    </>
  );
}
