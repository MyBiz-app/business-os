import { Check, ShieldCheck } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { ChatMock, DashboardMock, PhoneMock } from "@/components/marketing/mocks";
import { CtaBand, Faq, FeatureGrid, IndustryCards, SectionHeading } from "@/components/marketing/sections";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.meta");
  const tApp = await getTranslations("app");
  return { title: t("home"), description: tApp("tagline") };
}

/** The marketing home page: what MyBiz is and why, for business owners. */
export default async function Home() {
  const t = await getTranslations("marketing");
  const trust = t.raw("trust.items") as string[];
  const steps = t.raw("steps.items") as { title: string; text: string }[];

  return (
    <main className="enter flex flex-col">
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div aria-hidden="true" className="pointer-events-none absolute -top-40 start-1/2 size-[36rem] -translate-x-1/2 rounded-full bg-gradient-to-br from-indigo-500/25 to-fuchsia-500/25 blur-3xl rtl:translate-x-1/2" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-6 py-16 lg:grid-cols-2 lg:py-24">
          <div className="flex flex-col items-start gap-6">
            <p className="rounded-full bg-surface px-4 py-1.5 text-sm font-medium text-primary shadow-sm ring-1 ring-border">
              {t("hero.eyebrow")}
            </p>
            <h1 className="text-5xl font-extrabold leading-[1.05] tracking-tight sm:text-6xl">
              {t("hero.title")}{" "}
              <span className="bg-gradient-to-br from-indigo-500 to-fuchsia-500 bg-clip-text text-transparent">
                {t("hero.titleAccent")}
              </span>
            </h1>
            <p className="max-w-xl text-lg text-muted sm:text-xl">{t("hero.subtitle")}</p>
            <div className="flex flex-wrap gap-3">
              <Link href="/signup" className="btn-primary px-6 py-3 text-lg">
                {t("hero.ctaPrimary")}
              </Link>
              <Link href="/features" className="btn-secondary px-6 py-3 text-lg">
                {t("hero.ctaSecondary")}
              </Link>
            </div>
            <p className="text-sm text-muted">{t("hero.note")}</p>
          </div>
          <div className="relative">
            <DashboardMock />
            <div className="absolute -bottom-10 -start-4 hidden w-72 sm:block">
              <ChatMock question={t("mock.ai")} answer={t("mock.aiAnswer")} />
            </div>
          </div>
        </div>
      </section>

      {/* Trust strip */}
      <section aria-label={t("hero.eyebrow")} className="border-y border-border bg-surface/60">
        <ul className="mx-auto grid max-w-6xl gap-4 px-6 py-6 text-sm font-medium sm:grid-cols-2 lg:grid-cols-4">
          {trust.map((item) => (
            <li key={item} className="flex items-center gap-2">
              <ShieldCheck aria-hidden="true" className="size-5 shrink-0 text-primary" />
              {item}
            </li>
          ))}
        </ul>
      </section>

      <FeatureGrid />

      {/* AI assistant */}
      <section aria-labelledby="ai-heading" className="bg-surface/60 py-20">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 lg:grid-cols-2">
          <div className="flex flex-col gap-5">
            <p className="text-sm font-semibold text-primary">{t("ai.eyebrow")}</p>
            <h2 id="ai-heading" className="text-3xl font-bold tracking-tight sm:text-4xl">
              {t("ai.title")}
            </h2>
            <p className="text-lg text-muted">{t("ai.text")}</p>
            <ul className="flex flex-col gap-2">
              {(t.raw("ai.points") as string[]).map((point) => (
                <li key={point} className="flex items-center gap-2 font-medium">
                  <Check aria-hidden="true" className="size-5 text-success" />
                  {point}
                </li>
              ))}
            </ul>
          </div>
          <ChatMock question={t("ai.q")} answer={t("ai.a")} />
        </div>
      </section>

      {/* Client app */}
      <section aria-labelledby="app-heading" className="py-20">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 lg:grid-cols-2">
          <PhoneMock />
          <div className="flex flex-col gap-5">
            <p className="text-sm font-semibold text-primary">{t("app.eyebrow")}</p>
            <h2 id="app-heading" className="text-3xl font-bold tracking-tight sm:text-4xl">
              {t("app.title")}
            </h2>
            <p className="text-lg text-muted">{t("app.text")}</p>
            <ul className="flex flex-col gap-2">
              {(t.raw("app.points") as string[]).map((point) => (
                <li key={point} className="flex items-center gap-2 font-medium">
                  <Check aria-hidden="true" className="size-5 text-success" />
                  {point}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <IndustryCards />

      {/* How it works */}
      <section aria-labelledby="steps-heading" className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-6 py-20">
        <SectionHeading id="steps-heading" title={t("steps.title")} />
        <ol className="grid gap-4 md:grid-cols-3">
          {steps.map((step, index) => (
            <li key={step.title} className="card flex flex-col gap-3 p-6">
              <span aria-hidden="true" className="btn-primary size-10 text-lg">
                {index + 1}
              </span>
              <h3 className="text-lg font-semibold">{step.title}</h3>
              <p className="text-muted">{step.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <Faq />
      <CtaBand />
    </main>
  );
}
