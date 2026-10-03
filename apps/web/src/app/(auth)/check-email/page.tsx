import { getTranslations } from "next-intl/server";
import Link from "next/link";

export default async function CheckEmailPage({ searchParams }: PageProps<"/check-email">) {
  const t = await getTranslations("auth.checkEmail");
  const { email } = await searchParams;
  const devMailbox = process.env.NODE_ENV === "development" ? process.env.NEXT_PUBLIC_DEV_MAILBOX_URL : undefined;

  return (
    <>
      <h1 className="text-2xl font-bold">{t("title")}</h1>
      <p>{t("body", { email: typeof email === "string" ? email : "" })}</p>
      {devMailbox && (
        <p className="rounded-lg border border-border bg-background px-3 py-2 text-sm">
          {t("devMailbox")}:{" "}
          <a href={devMailbox} target="_blank" rel="noreferrer" className="text-primary underline" dir="ltr">
            {devMailbox}
          </a>
        </p>
      )}
      <Link href="/login" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("backToLogin")}
      </Link>
    </>
  );
}
