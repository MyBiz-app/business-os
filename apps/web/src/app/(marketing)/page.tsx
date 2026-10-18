import { Check, ShieldCheck } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { Container } from "@/components/layout/container";
import { Section } from "@/components/layout/section";
import {
  ChatMock,
  DashboardMock,
} from "@/components/marketing/mocks";
import {
  AboutTeaser,
  BentoFeatures,
  DemoSection,
  FactsStrip,
  PricingTeaser,
} from "@/components/marketing/home";
import { AiTeamSection } from "@/components/marketing/ai-team-sections";
import { HomePhone } from "@/components/marketing/home-phone";
import { HeroIntro } from "@/components/marketing/hero-intro";
import { Reveal } from "@/components/marketing/reveal";
import {
  BranchesSection,
  CtaBand,
  Faq,
  IndustryCards,
  SectionHeading,
} from "@/components/marketing/sections";
import {
  FaqData,
  OrganizationData,
} from "@/components/marketing/structured-data";

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
    <main id="main" className="enter flex flex-col">
      <OrganizationData />
      <FaqData />
      <HeroIntro />
      {/* Hero */}
      <Section
        id="hero"
        tone="inverse"
        spacing="loose"
        className="relative isolate overflow-hidden"
        innerClassName="grid items-center gap-14 lg:grid-cols-[1.05fr_1fr] lg:gap-20"
      >
        <div
          aria-hidden="true"
          className="mk-grid pointer-events-none absolute inset-0 -z-10"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-32 start-[10%] -z-10 size-[34rem] rounded-full bg-primary/40 blur-[120px]"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-40 end-[5%] -z-10 size-[30rem] rounded-full bg-electric/25 blur-[120px]"
        />
        <div className="flex flex-col items-start gap-7">
          <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-sm font-medium text-white/85 backdrop-blur">
            <span
              aria-hidden="true"
              className="size-2 rounded-full bg-electric shadow-[0_0_10px] shadow-electric"
            />
            {t("hero.eyebrow")}
          </p>
          <h1 className="text-5xl font-extrabold leading-[1.04] tracking-tight sm:text-6xl lg:text-7xl">
            {t("hero.title")}{" "}
            <span className="bg-gradient-to-l from-electric to-[#60a5fa] bg-clip-text text-transparent">
              {t("hero.titleAccent")}
            </span>
          </h1>
          <p className="max-w-xl text-lg leading-relaxed text-white/75 sm:text-xl">
            {t("hero.subtitle")}
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/start"
              className="btn-primary btn-lg rounded-full px-7"
            >
              {t("hero.ctaPrimary")}
            </Link>
            <Link
              href="#features"
              className="btn-lg inline-flex items-center justify-center rounded-full border border-white/25 px-7 font-semibold text-white transition-colors hover:bg-white/10"
            >
              {t("hero.ctaSecondary")}
            </Link>
          </div>
          <p className="text-sm text-white/60">{t("hero.note")}</p>
        </div>
        <div className="relative pb-10">
          <div className="mk-float">
            <DashboardMock />
          </div>
          <div className="absolute -bottom-2 -start-4 hidden w-72 sm:block">
            <ChatMock
              tone="ai"
              question={t("mock.ai")}
              answer={t("mock.aiAnswer")}
            />
          </div>
        </div>
      </Section>

      {/* Trust strip */}
      <section
        aria-label={t("hero.eyebrow")}
        className="border-b border-border bg-surface"
      >
        <Container
          as="ul"
          className="grid gap-4 py-6 text-sm font-semibold sm:grid-cols-2 lg:grid-cols-4"
        >
          {trust.map((item) => (
            <li key={item} className="flex items-center gap-2">
              <ShieldCheck
                aria-hidden="true"
                className="size-5 shrink-0 text-success-ink"
              />
              {item}
            </li>
          ))}
        </Container>
      </section>

      <FactsStrip />

      <BentoFeatures />

      <DemoSection />

      <AiTeamSection />

      {/* AI assistant */}
      <Section
        tone="inverse"
        aria-labelledby="ai-heading"
        className="relative isolate overflow-hidden"
        innerClassName="grid items-center gap-12 lg:grid-cols-2 lg:gap-20"
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-24 end-[10%] -z-10 size-[28rem] rounded-full bg-ai/40 blur-[110px]"
        />
        <Reveal className="flex max-w-xl flex-col gap-5">
          <p className="text-sm font-semibold text-[#c4b5fd]">
            {t("ai.eyebrow")}
          </p>
          <h2
            id="ai-heading"
            className="text-3xl font-extrabold tracking-tight sm:text-5xl"
          >
            {t("ai.title")}
          </h2>
          <p className="text-lg leading-relaxed text-white/75">
            {t("ai.text")}
          </p>
          <ul className="flex flex-col gap-2">
            {(t.raw("ai.points") as string[]).map((point) => (
              <li key={point} className="flex items-center gap-2 font-medium">
                <Check aria-hidden="true" className="size-5 text-electric" />
                {point}
              </li>
            ))}
          </ul>
        </Reveal>
        <Reveal delay={100}>
          <ChatMock tone="ai" question={t("ai.q")} answer={t("ai.a")} />
        </Reveal>
      </Section>

      {/* Client app */}
      <Section
        aria-labelledby="app-heading"
        innerClassName="grid items-center gap-12 lg:grid-cols-2 lg:gap-20"
      >
        <Reveal>
          <HomePhone />
        </Reveal>
        <Reveal className="flex max-w-xl flex-col gap-5">
          <p className="text-sm font-semibold text-primary-ink">
            {t("app.eyebrow")}
          </p>
          <h2
            id="app-heading"
            className="text-3xl font-bold tracking-tight sm:text-4xl"
          >
            {t("app.title")}
          </h2>
          <p className="text-lg text-muted">{t("app.text")}</p>
          <ul className="flex flex-col gap-2">
            {(t.raw("app.points") as string[]).map((point) => (
              <li key={point} className="flex items-center gap-2 font-medium">
                <Check aria-hidden="true" className="size-5 text-success-ink" />
                {point}
              </li>
            ))}
          </ul>
        </Reveal>
      </Section>

      <BranchesSection />

      <IndustryCards />

      <PricingTeaser />

      {/* How it works */}
      <Section
        aria-labelledby="steps-heading"
        innerClassName="flex flex-col gap-10"
      >
        <SectionHeading id="steps-heading" title={t("steps.title")} />
        <ol tabIndex={0} aria-labelledby="steps-heading" className="swipe gap-4 sm:grid md:grid-cols-3">
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
      </Section>

      <Faq />
      <AboutTeaser />
      <CtaBand />
    </main>
  );
}
