import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { AuthHeading } from "@/components/auth/auth-shell";
import { codeChannels } from "@/lib/auth-providers";
import { safeNext } from "@/lib/navigation";

import { CodeLoginForm } from "./code-form";

export default async function CodeLoginPage({ searchParams }: PageProps<"/login/code">) {
  const t = await getTranslations("auth");
  const { next } = await searchParams;
  const nextPath = safeNext(next) ?? undefined;
  const channels = await codeChannels();

  return (
    <>
      <AuthHeading title={t("codeLogin.title")} subtitle={t("codeLogin.subtitle")} />
      <CodeLoginForm channels={channels} next={nextPath} />
      <Link href={nextPath ? `/login?next=${encodeURIComponent(nextPath)}` : "/login"} className="text-sm text-primary-ink underline underline-offset-4">
        {t("codeLogin.usePassword")}
      </Link>
    </>
  );
}
