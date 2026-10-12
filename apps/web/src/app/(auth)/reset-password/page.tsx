import { getTranslations } from "next-intl/server";

import { ResetForm } from "./reset-form";

export default async function ResetPasswordPage() {
  const t = await getTranslations("auth.reset");

  return (
    <>
      <h1 className="text-3xl font-extrabold tracking-tight">{t("title")}</h1>
      <ResetForm />
    </>
  );
}
