import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { AppHeader } from "@/components/app-header";
import { isApiHealthy } from "@/lib/api";

export default async function Home() {
  const t = await getTranslations();
  const apiOnline = await isApiHealthy();

  return (
    <div className="flex flex-1 flex-col">
      <AppHeader />

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-8 px-6 py-16">
        <div className="flex flex-col gap-3">
          <h1 className="text-4xl font-bold tracking-tight">{t("app.name")}</h1>
          <p className="text-lg text-muted">{t("app.tagline")}</p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Link href="/signup" className="rounded-lg bg-primary px-5 py-2.5 font-semibold text-on-primary">
            {t("home.signup")}
          </Link>
          <Link href="/login" className="rounded-lg border border-border px-5 py-2.5 font-semibold">
            {t("home.login")}
          </Link>
        </div>

        <section aria-labelledby="status-heading" className="rounded-xl border border-border bg-surface p-5">
          <h2 id="status-heading" className="mb-3 text-sm font-semibold text-muted">
            {t("home.status")}
          </h2>
          <p className="flex items-center gap-2" role="status">
            <span
              aria-hidden="true"
              className={`inline-block size-2.5 rounded-full ${apiOnline ? "bg-success" : "bg-danger"}`}
            />
            {apiOnline ? t("home.apiOnline") : t("home.apiOffline")}
          </p>
        </section>
      </main>
    </div>
  );
}
