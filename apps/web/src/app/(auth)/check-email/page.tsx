import { MailCheck } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { AuthHeading } from "@/components/auth/auth-shell";
import { isolate } from "@/lib/bidi";

export default async function CheckEmailPage({ searchParams }: PageProps<"/check-email">) {
  const t = await getTranslations("auth.checkEmail");
  const { email } = await searchParams;
  const devMailbox = process.env.NODE_ENV === "development" ? process.env.NEXT_PUBLIC_DEV_MAILBOX_URL : undefined;

  return (
    <>
      <AuthHeading title={t("title")} icon={<MailCheck className="size-6" />} />
      <p>{t("body", { email: isolate(typeof email === "string" ? email : "") })}</p>
      <p className="text-sm text-muted">{t("hint")}</p>
      {devMailbox && (
        <p className="rounded-xl border border-border bg-surface px-3 py-2 text-sm">
          {t("devMailbox")}:{" "}
          <a href={devMailbox} target="_blank" rel="noreferrer" className="text-primary-ink underline" dir="ltr">
            {devMailbox}
          </a>
        </p>
      )}
      <Link href="/login" className="btn-secondary px-4 py-2.5 text-center">
        {t("backToLogin")}
      </Link>
    </>
  );
}
