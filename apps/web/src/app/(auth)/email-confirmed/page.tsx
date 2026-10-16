import { MailCheck, MailX } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { AuthHeading } from "@/components/auth/auth-shell";

/** Where the link in a contact-email confirmation lands (the API redirects here). */
export default async function EmailConfirmedPage({ searchParams }: PageProps<"/email-confirmed">) {
  const t = await getTranslations("emailConfirmed");
  const { status } = await searchParams;
  const ok = status === "ok";

  return (
    <>
      <AuthHeading title={ok ? t("okTitle") : t("badTitle")} icon={ok ? <MailCheck className="size-6" /> : <MailX className="size-6" />} />
      <p>{ok ? t("okText") : t("badText")}</p>
      <Link href="/" className="btn-secondary px-4 py-2.5 text-center">
        {t("home")}
      </Link>
    </>
  );
}
