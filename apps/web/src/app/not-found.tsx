import { getTranslations } from "next-intl/server";
import Link from "next/link";

export default async function NotFound() {
  const t = await getTranslations("errorPages");

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-4 px-4 py-16 text-center">
      <h1 className="text-2xl font-semibold">{t("notFoundTitle")}</h1>
      <p className="text-muted">{t("notFoundText")}</p>
      <Link href="/" className="btn-primary px-4 py-2">
        {t("home")}
      </Link>
    </main>
  );
}
