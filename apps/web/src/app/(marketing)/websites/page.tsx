import { Check } from "lucide-react";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { Section } from "@/components/layout/section";
import { Reveal } from "@/components/marketing/reveal";
import { CtaBand, SectionHeading } from "@/components/marketing/sections";
import { BandText } from "@/components/marketing/subpage";
import { WebsiteLeadDemo } from "@/components/marketing/website-lead-demo";
import { WebsitesShowcase, type ShowcaseSite } from "@/components/marketing/websites-showcase";
import { loadCatalog, loadSitePrices } from "@/lib/pricing";
import { formatMoney } from "@/lib/money";

const SITES = [
  { key: "barber", tone: "bg-gradient-to-br from-navy to-primary" },
  { key: "gym", tone: "bg-gradient-to-br from-ai to-primary" },
  { key: "pizza", tone: "bg-gradient-to-br from-warning to-danger" },
] as const;

const CURRENCIES = ["ILS", "USD", "EUR"] as const;

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.meta");
  return { title: `${t("websites")} · ${BRAND.name}` };
}

/** "A website for your business", in the style of a product page: one big idea per screen. */
export default async function WebsitesPage({ searchParams }: PageProps<"/websites">) {
  const t = await getTranslations("marketing.websites");
  const locale = await getLocale();
  const query = await searchParams;
  const requested = typeof query.currency === "string" ? query.currency : "";
  const currency = (CURRENCIES as readonly string[]).includes(requested) ? requested : locale === "he" ? "ILS" : "USD";
  const money = (amount: number) => formatMoney(amount, currency, locale);
  const [catalog, sitePrices] = await Promise.all([loadCatalog(currency), loadSitePrices(currency)]);
  const alone = sitePrices?.landing_only;
  const withSystem = sitePrices?.landing_with_system;
  const systemFrom = catalog?.core[0]?.price;

  const sites: ShowcaseSite[] = SITES.map(({ key, tone }) => ({
    key,
    tone,
    label: t(`sites.${key}.label`),
    name: t(`sites.${key}.name`),
    line: t(`sites.${key}.line`),
    button: t(`sites.${key}.button`),
    items: t.raw(`sites.${key}.items`) as string[],
  }));
  const steps = t.raw("steps.items") as { title: string; text: string }[];
  const cards = [
    { key: "siteOnly", setup: alone?.setup ?? null, monthly: alone?.monthly ?? null, href: "/start", featured: false },
    { key: "systemOnly", setup: null, monthly: systemFrom ?? null, href: "/pricing", featured: false },
    { key: "both", setup: withSystem?.setup ?? null, monthly: withSystem?.monthly ?? null, href: "/start", featured: true },
  ] as const;
  const saved = alone && withSystem ? alone.setup - withSystem.setup : null;

  return (
    <main id="main" className="enter flex flex-col">
      <header className="section-inverse relative isolate w-full overflow-hidden bg-navy px-4 pb-12 pt-16 text-center text-white sm:pt-24">
        <div aria-hidden="true" className="mk-grid pointer-events-none absolute inset-0 -z-10" />
        <div aria-hidden="true" className="pointer-events-none absolute -top-40 start-[20%] -z-10 size-[30rem] rounded-full bg-primary/35 blur-[120px]" />
        <h1 className="mx-auto max-w-4xl text-5xl font-extrabold leading-[1.05] tracking-tight text-balance sm:text-7xl">{t("title")}</h1>
        <p className="mx-auto mt-6 max-w-2xl text-xl text-white/75 text-pretty">{t("subtitle")}</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/start" className="btn-primary btn-lg rounded-full px-7">{t("start")}</Link>
          <a href="#prices" className="rounded-full border border-white/25 px-7 py-3 text-base font-semibold hover:bg-white/10">{t("seePrices")}</a>
        </div>
      </header>

      <WebsitesShowcase sites={sites} heading={t("showcase")} caption={t("showcaseCaption")} />

      <Section tone="surface" aria-labelledby="how-heading" innerClassName="flex flex-col gap-12">
        <Reveal><SectionHeading id="how-heading" title={t("steps.title")} /></Reveal>
        <ol className="grid gap-8 md:grid-cols-3">
          {steps.map((step, i) => (
            <li key={step.title}>
              <Reveal delay={i * 120} className="flex flex-col gap-3">
                <span className="text-6xl font-extrabold tracking-tight text-primary-ink tabular-nums">{i + 1}</span>
                <h3 className="text-2xl font-bold">{step.title}</h3>
                <p className="text-lg text-muted text-pretty">{step.text}</p>
              </Reveal>
            </li>
          ))}
        </ol>
      </Section>

      <Section aria-labelledby="combo-heading" innerClassName="flex flex-col gap-10">
        <Reveal><BandText id="combo-heading" eyebrow={t("combo.eyebrow")} title={t("combo.title")} text={t("combo.text")} /></Reveal>
        <WebsiteLeadDemo
          labels={{
            site: t("combo.site"), crm: t("combo.crm"), name: t("combo.name"), phone: t("combo.phone"), send: t("combo.send"),
            sent: t("combo.sent"), lead: t("combo.lead"), source: t("combo.source"), fromSite: t("combo.fromSite"),
            person: t("combo.person"), phoneValue: "050-000-0000",
          }}
        />
      </Section>

      <Section tone="muted" id="prices" aria-labelledby="prices-heading" innerClassName="flex flex-col gap-10">
        <SectionHeading id="prices-heading" title={t("prices.title")} subtitle={t("prices.subtitle")} />
        <nav aria-label={t("prices.currency")} className="mx-auto flex gap-1 rounded-xl border border-border bg-surface p-1 text-sm shadow-sm">
          {CURRENCIES.map((code) => (
            <Link
              scroll={false}
              key={code}
              href={`/websites?currency=${code}#prices`}
              aria-current={code === currency ? "page" : undefined}
              className={`rounded-lg px-3 py-1 font-medium ${code === currency ? "bg-primary text-on-primary" : "hover:bg-foreground/5"}`}
            >
              {code}
            </Link>
          ))}
        </nav>
        <div className="grid gap-6 md:grid-cols-3">
          {cards.map((card) => (
            <article key={card.key} className={`relative flex flex-col gap-5 p-7 ${card.featured ? "card-accent shadow-xl md:-translate-y-2" : "card"}`}>
              {card.featured && <p className="absolute -top-3 start-6 rounded-full bg-primary px-3 py-1 text-xs font-bold text-on-primary shadow">{t("prices.recommended")}</p>}
              <h3 className="text-xl font-bold">{t(`prices.${card.key}.name`)}</h3>
              <p className="text-sm text-muted">{t(`prices.${card.key}.text`)}</p>
              <div className="flex flex-col gap-1">
                {card.setup !== null && (
                  <p className="text-4xl font-extrabold tracking-tight">
                    <bdi>{money(card.setup)}</bdi> <span className="text-sm font-medium text-muted">{t("prices.once")}</span>
                  </p>
                )}
                {card.monthly !== null && (
                  <p className={card.setup === null ? "text-4xl font-extrabold tracking-tight" : "text-lg font-semibold"}>
                    {card.setup === null && <span className="text-sm font-medium text-muted">{t("prices.from")} </span>}
                    <bdi>{money(card.monthly)}</bdi> <span className="text-sm font-medium text-muted">{t("prices.perMonth")}</span>
                  </p>
                )}
              </div>
              <ul className="flex flex-col gap-2 text-sm">
                {(t.raw(`prices.${card.key}.points`) as string[]).map((point) => (
                  <li key={point} className="flex items-start gap-2">
                    <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success-ink" />
                    {point}
                  </li>
                ))}
                {card.featured && saved !== null && (
                  <li className="flex items-start gap-2 font-semibold text-success-ink">
                    <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                    {t("prices.saving", { amount: money(saved) })}
                  </li>
                )}
              </ul>
              <Link href={card.href} className={`mt-auto rounded-full px-5 py-3 text-center ${card.featured ? "btn-primary" : "btn-secondary"}`}>
                {t(`prices.${card.key}.cta`)}
              </Link>
            </article>
          ))}
        </div>
        <p className="text-center text-sm text-muted">{t("prices.note")}</p>
      </Section>

      <Section aria-labelledby="gallery-heading" innerClassName="flex flex-col gap-10">
        <SectionHeading id="gallery-heading" title={t("gallery.title")} subtitle={t("gallery.subtitle")} />
        <ul className="grid gap-6 md:grid-cols-3">
          {SITES.map(({ key, tone }, i) => (
            <li key={key}>
              <Reveal delay={i * 100} className="card overflow-hidden">
                <div aria-hidden="true" className={`flex h-44 flex-col justify-end gap-1 p-5 text-white ${tone}`}>
                  <p className="text-xs font-semibold uppercase tracking-wide opacity-80">{t(`sites.${key}.name`)}</p>
                  <p className="text-xl font-extrabold leading-tight">{t(`sites.${key}.line`)}</p>
                </div>
                <p className="p-4 text-sm font-semibold">{t(`sites.${key}.label`)}</p>
              </Reveal>
            </li>
          ))}
        </ul>
        <p className="text-center text-sm text-muted">{t("gallery.note")}</p>
      </Section>

      <Section tone="surface" aria-labelledby="faq-heading" innerClassName="flex flex-col gap-8">
        <SectionHeading id="faq-heading" title={t("faq.title")} />
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-3">
          {(t.raw("faq.items") as { q: string; a: string }[]).map((item) => (
            <details key={item.q} className="card group p-5 open:shadow-md">
              <summary className="cursor-pointer list-none font-semibold">{item.q}</summary>
              <p className="mt-3 text-muted">{item.a}</p>
            </details>
          ))}
        </div>
      </Section>
      <CtaBand />
    </main>
  );
}
