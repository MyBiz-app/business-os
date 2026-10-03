import { getTranslations } from "next-intl/server";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { isApiHealthy } from "@/lib/api";

export default async function Home() {
  const t = await getTranslations();
  const apiOnline = await isApiHealthy();

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border px-6 py-4">
        <span className="text-lg font-bold">{t("app.name")}</span>
        <div className="flex flex-wrap items-center gap-4">
          <LocaleSwitcher />
          <ThemeSwitcher />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-8 px-6 py-16">
        <div className="flex flex-col gap-3">
          <h1 className="text-4xl font-bold tracking-tight">{t("app.name")}</h1>
          <p className="text-lg text-muted">{t("app.tagline")}</p>
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

        <p className="text-sm text-muted">{t("home.comingSoon")}</p>
      </main>
    </div>
  );
}
