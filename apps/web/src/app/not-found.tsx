import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { StatusPage } from "@/components/layout/status-page";

export default async function NotFound() {
  const t = await getTranslations("errorPages");

  return (
    <StatusPage title={t("notFoundTitle")} text={t("notFoundText")}>
      <Link href="/" className="btn-primary rounded-full px-6 py-2.5">
        {t("home")}
      </Link>
    </StatusPage>
  );
}
