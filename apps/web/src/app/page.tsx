import { Bot, CalendarDays, Smartphone, Users } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { AppHeader } from "@/components/app-header";
import { isApiHealthy } from "@/lib/api";

const FEATURES = [
  { key: "schedule", Icon: CalendarDays },
  { key: "clients", Icon: Users },
  { key: "app", Icon: Smartphone },
  { key: "ai", Icon: Bot },
] as const;

export default async function Home() {
  const t = await getTranslations();
  const apiOnline = await isApiHealthy();

  return (
    <div className="flex flex-1 flex-col">
      <AppHeader />

      <main className="enter mx-auto flex w-full max-w-5xl flex-1 flex-col justify-center gap-12 px-6 py-16">
        <div className="relative flex flex-col items-center gap-5 text-center">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -top-24 size-80 rounded-full bg-gradient-to-br from-indigo-500/25 to-fuchsia-500/25 blur-3xl"
          />
          <p className="relative rounded-full bg-surface px-4 py-1.5 text-sm font-medium text-primary shadow-sm ring-1 ring-border">
            {t("home.eyebrow")}
          </p>
          <h1 className="relative bg-gradient-to-br from-foreground to-foreground/60 bg-clip-text pb-1 text-5xl font-extrabold tracking-tight text-transparent sm:text-6xl">
            {t("app.name")}
          </h1>
          <p className="relative max-w-xl text-lg text-muted sm:text-xl">{t("app.tagline")}</p>
          <div className="relative flex flex-wrap justify-center gap-3 pt-2">
            <Link href="/signup" className="btn-primary px-6 py-3 text-lg">
              {t("home.signup")}
            </Link>
            <Link href="/login" className="btn-secondary px-6 py-3 text-lg">
              {t("home.login")}
            </Link>
          </div>
        </div>

        <ul className="enter-items grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map(({ key, Icon }) => (
            <li key={key} className="card card-hover flex flex-col gap-3 p-5">
              <span className="icon-tile size-11">
                <Icon aria-hidden="true" className="size-5" />
              </span>
              <h2 className="font-semibold">{t(`home.features.${key}.title`)}</h2>
              <p className="text-sm text-muted">{t(`home.features.${key}.text`)}</p>
            </li>
          ))}
        </ul>

        <section aria-labelledby="status-heading" className="flex items-center justify-center gap-2 text-sm text-muted">
          <h2 id="status-heading" className="sr-only">
            {t("home.status")}
          </h2>
          <p className="flex items-center gap-2" role="status">
            <span aria-hidden="true" className={`relative flex size-2.5`}>
              {apiOnline && <span className="absolute inline-flex size-full animate-ping rounded-full bg-success opacity-60" />}
              <span className={`relative inline-flex size-2.5 rounded-full ${apiOnline ? "bg-success" : "bg-danger"}`} />
            </span>
            {apiOnline ? t("home.apiOnline") : t("home.apiOffline")}
          </p>
        </section>
      </main>
    </div>
  );
}
