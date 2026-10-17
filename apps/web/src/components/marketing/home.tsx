import { categories } from "@business-os/verticals";
import { ArrowLeft, Check, Sparkles } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Section } from "@/components/layout/section";
import { DemoStage } from "@/components/marketing/demo-stage";
import { MiniLoop } from "@/components/marketing/mini-loops";
import { PricingCalculator } from "@/components/marketing/pricing-calculator";
import { Reveal } from "@/components/marketing/reveal";
import { FEATURES, SectionHeading } from "@/components/marketing/sections";
import { loadCatalog } from "@/lib/pricing";
import { formatMoney } from "@/lib/money";

/** Facts counted from the product itself, so they never go stale and are never invented. */
export async function FactsStrip() {
  const t = await getTranslations("marketing.home.facts");
  const facts = [
    { value: FEATURES.length, label: t("modules") },
    { value: categories().filter((c) => c.status !== "planned").length, label: t("industries") },
    { value: 3, label: t("apps") },
    { value: 2, label: t("languages") },
  ];
  return (
    <Section aria-label={t("label")} spacing="compact">
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-3xl bg-border shadow-[0_1px_2px_rgb(17_24_39/0.06)] lg:grid-cols-4">
        {facts.map(({ value, label }) => (
          <div key={label} className="flex flex-col items-center gap-1 bg-surface px-4 py-7 text-center">
            <dd className="order-1 bg-gradient-to-br from-primary to-electric bg-clip-text text-4xl font-extrabold tracking-tight text-transparent tabular-nums">{value}</dd>
            <dt className="order-2 text-sm font-medium text-muted">{label}</dt>
          </div>
        ))}
      </dl>
    </Section>
  );
}

const BENTO = [
  { key: "schedule", span: "lg:col-span-3", tone: "primary" },
  { key: "ai", span: "lg:col-span-3", tone: "ai" },
  { key: "clients", span: "lg:col-span-2", tone: "primary" },
  { key: "app", span: "lg:col-span-2", tone: "primary" },
  { key: "reports", span: "lg:col-span-2", tone: "primary" },
] as const;

/** The headline abilities as a bento grid, then the rest as a quiet list. */
export async function BentoFeatures() {
  const t = await getTranslations("marketing.features");
  const th = await getTranslations("marketing.home");
  const lead = new Set<string>(BENTO.map((b) => b.key));
  const rest = FEATURES.filter(({ key }) => !lead.has(key));
  return (
    <Section id="features" aria-labelledby="features-heading" className="scroll-mt-20" innerClassName="flex flex-col gap-10">
      <Reveal>
        <SectionHeading id="features-heading" eyebrow={th("bento.eyebrow")} title={t("title")} subtitle={t("subtitle")} />
      </Reveal>
      <ul className="grid gap-4 lg:grid-cols-6">
        {BENTO.map(({ key, span, tone }, index) => {
          const Icon = FEATURES.find((f) => f.key === key)!.Icon;
          const ai = tone === "ai";
          return (
            <li key={key} className={span}>
              <Reveal delay={index * 60} className="h-full">
                <article
                  className={`card card-hover flex h-full flex-col gap-4 p-7 ${ai ? "border-ai/25 bg-gradient-to-br from-ai/[0.07] to-surface" : ""}`}
                >
                  <span
                    className={`inline-flex size-12 items-center justify-center rounded-2xl ${ai ? "bg-ai text-white shadow-lg shadow-ai/30" : "bg-primary/10 text-primary-ink"}`}
                  >
                    <Icon aria-hidden="true" className="size-6" />
                  </span>
                  <h3 className="text-xl font-bold tracking-tight">{t(`items.${key}.title`)}</h3>
                  <p className="text-muted">{t(`items.${key}.text`)}</p>
                  <MiniLoop kind={key} />
                </article>
              </Reveal>
            </li>
          );
        })}
      </ul>
      <Reveal>
        <p className="mb-3 text-center text-sm font-semibold text-muted">{th("bento.more")}</p>
        <ul className="flex flex-wrap justify-center gap-2">
          {rest.map(({ key, Icon }) => (
            <li key={key} className="flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium shadow-sm">
              <Icon aria-hidden="true" className="size-4 text-primary-ink" />
              {t(`items.${key}.title`)}
            </li>
          ))}
        </ul>
      </Reveal>
    </Section>
  );
}

const PRESETS = ["starter", "growing", "ai_powered"] as const;

/** The three recommended plans, with the live starting price. This is the "low cost" promise:
 * a small base price, no set-up fee, and modules only when wanted. */
export async function PricingTeaser() {
  const t = await getTranslations("marketing.pricing");
  const th = await getTranslations("marketing.home.pricing");
  const tModules = await getTranslations("modules");
  const locale = await getLocale();
  const currency = locale === "he" ? "ILS" : "USD";
  const catalog = await loadCatalog(currency);
  const base = catalog?.core[0]?.price ?? 0;
  const priceOf = (key: string) => catalog?.modules.find((m) => m.key === key)?.price ?? 0;
  const presetPrice = (preset: (typeof PRESETS)[number]) => base + (catalog?.presets[preset] ?? []).reduce((sum, key) => sum + priceOf(key), 0);
  return (
    <Section id="pricing" aria-labelledby="pricing-heading" className="scroll-mt-20 bg-gradient-to-b from-background to-primary/[0.06]" innerClassName="flex flex-col gap-10">
      <>
        <Reveal>
          <SectionHeading id="pricing-heading" eyebrow={th("eyebrow")} title={t("title")} subtitle={t("subtitle")} />
        </Reveal>
        <Reveal>
          <ul className="mx-auto flex flex-wrap justify-center gap-3 text-sm font-semibold">
            {(th.raw("points") as string[]).map((point) => (
              <li key={point} className="flex items-center gap-2 rounded-full bg-surface px-4 py-2 shadow-sm ring-1 ring-border">
                <Check aria-hidden="true" className="size-4 text-success-ink" />
                {point}
              </li>
            ))}
          </ul>
        </Reveal>
        {catalog && (
          <ul className="grid gap-5 md:grid-cols-3">
            {PRESETS.map((preset, index) => {
              const popular = preset === "growing";
              return (
                <li key={preset}>
                  <Reveal delay={index * 70} className="h-full">
                    <article className={`relative flex h-full flex-col gap-5 p-7 ${popular ? "card-accent shadow-xl md:-translate-y-2" : "card"}`}>
                      {popular && <p className="absolute -top-3 start-6 rounded-full bg-primary px-3 py-1 text-xs font-bold text-on-primary shadow">{t("popular")}</p>}
                      <h3 className="text-xl font-bold">{t(`presets.${preset}`)}</h3>
                      <p className="text-sm text-muted">{t(`presetText.${preset}`)}</p>
                      <p className="flex items-baseline gap-1">
                        <span className="text-sm text-muted">{t("from")}</span>
                        <span className="text-4xl font-extrabold tracking-tight">
                          <bdi>{formatMoney(presetPrice(preset), currency, locale)}</bdi>
                        </span>
                        <span className="text-sm text-muted">{t("perMonth")}</span>
                      </p>
                      <ul className="flex flex-col gap-2 text-sm">
                        <li className="flex items-start gap-2">
                          <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success-ink" />
                          {t("coreText")}
                        </li>
                        {(catalog.presets[preset] ?? []).map((key) => (
                          <li key={key} className="flex items-start gap-2">
                            <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success-ink" />
                            {tModules(`names.${key}` as "names.client_app")}
                          </li>
                        ))}
                      </ul>
                      <Link href={`/start?preset=${preset}&currency=${currency}`} className={`mt-auto rounded-full px-5 py-3 ${popular ? "btn-primary" : "btn-secondary"}`}>
                        {t("cta")}
                      </Link>
                      <p className="text-center text-xs text-muted">{t("trialNote")}</p>
                    </article>
                  </Reveal>
                </li>
              );
            })}
          </ul>
        )}
        {catalog && (
          <Reveal>
            <PricingCalculator catalog={catalog} compact />
          </Reveal>
        )}
        <Link href="/pricing" className="group mx-auto inline-flex items-center gap-1 font-semibold text-primary-ink">
          {t("seeAll")}
          <ArrowLeft aria-hidden="true" className="size-4 transition-transform group-hover:-translate-x-1 ltr:rotate-180 ltr:group-hover:translate-x-1" />
        </Link>
      </>
    </Section>
  );
}

/** A short "about" with the four values, linking to the full page. */
export async function AboutTeaser() {
  const t = await getTranslations("marketing.about");
  const th = await getTranslations("marketing.home.about");
  const values = t.raw("values") as { title: string; text: string }[];
  return (
    <Section aria-labelledby="about-heading" innerClassName="grid gap-12 lg:grid-cols-[1fr_1.4fr] lg:gap-20">
      <Reveal className="flex flex-col items-start gap-5">
        <p className="text-sm font-semibold text-primary-ink">{th("eyebrow")}</p>
        <h2 id="about-heading" className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          {t("title")}
        </h2>
        <p className="text-lg text-muted">{t("intro")}</p>
        <Link href="/about" className="group inline-flex items-center gap-1 font-semibold text-primary-ink">
          {th("more")}
          <ArrowLeft aria-hidden="true" className="size-4 transition-transform group-hover:-translate-x-1 ltr:rotate-180 ltr:group-hover:translate-x-1" />
        </Link>
      </Reveal>
      <ul className="grid gap-4 sm:grid-cols-2">
        {values.map((value, index) => (
          <li key={value.title}>
            <Reveal delay={index * 60} className="h-full">
              <div className="card flex h-full flex-col gap-2 p-6">
                <Sparkles aria-hidden="true" className="size-5 text-electric" />
                <h3 className="font-bold">{value.title}</h3>
                <p className="text-sm text-muted">{value.text}</p>
              </div>
            </Reveal>
          </li>
        ))}
      </ul>
    </Section>
  );
}

/** The looping product tour ("a live video"): see components/marketing/demo-stage.tsx. */
export async function DemoSection() {
  const t = await getTranslations("marketing.home.demo");
  return (
    <Section id="demo" aria-labelledby="demo-heading" className="scroll-mt-20 !pt-0" innerClassName="flex flex-col gap-10">
      <Reveal>
        <SectionHeading id="demo-heading" eyebrow={t("eyebrow")} title={t("title")} subtitle={t("subtitle")} />
      </Reveal>
      <Reveal className="mx-auto w-full max-w-6xl">
        <DemoStage />
      </Reveal>
    </Section>
  );
}
