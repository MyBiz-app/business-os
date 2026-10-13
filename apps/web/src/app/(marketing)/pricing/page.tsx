import { Check, Minus } from "lucide-react";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { Container } from "@/components/layout/container";
import { Section } from "@/components/layout/section";
import { PricingCalculator } from "@/components/marketing/pricing-calculator";
import { CtaBand, Faq, PageHero, SectionHeading } from "@/components/marketing/sections";
import { FaqData, OrganizationData } from "@/components/marketing/structured-data";
import { ModuleIcon } from "@/components/modules/module-icon";
import { loadCatalog } from "@/lib/pricing";
import { formatMoney, toMajor } from "@/lib/money";

const CURRENCIES = ["ILS", "USD", "EUR"] as const;
const PRESETS = ["starter", "growing", "ai_powered"] as const;

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.meta");
  return { title: `${t("pricing")} · ${BRAND.name}` };
}

/** Prices from the API's module catalog: recommended plans, base tiers and every module. */
export default async function PricingPage({ searchParams }: PageProps<"/pricing">) {
  const t = await getTranslations("marketing.pricing");
  const th = await getTranslations("marketing.home.pricing");
  const tModules = await getTranslations("modules");
  const locale = await getLocale();
  const query = await searchParams;
  const requested = typeof query.currency === "string" ? query.currency : "";
  const currency = (CURRENCIES as readonly string[]).includes(requested) ? requested : locale === "he" ? "ILS" : "USD";
  const catalog = await loadCatalog(currency);
  const money = (amount: number) => formatMoney(amount, currency, locale);

  const base = catalog?.core[0]?.price ?? 0;
  const priceOf = (key: string) => catalog?.modules.find((m) => m.key === key)?.price ?? 0;
  const presetPrice = (preset: (typeof PRESETS)[number]) =>
    base + (catalog?.presets[preset] ?? []).reduce((sum, key) => sum + priceOf(key), 0);

  // Every module that appears in a recommended plan, for the comparison table.
  const compared = [...new Set(PRESETS.flatMap((preset) => catalog?.presets[preset] ?? []))];

  return (
    <main className="enter flex flex-col">
      {/* The starting price is the base tier, the same number the cards show. */}
      <OrganizationData price={toMajor(base, currency)} currency={currency} />
      <FaqData />
      <PageHero title={t("title")} subtitle={t("subtitle")}>
        <ul className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm font-semibold text-white/90">
          {(th.raw("points") as string[]).map((point) => (
            <li key={point} className="flex items-center gap-2">
              <Check aria-hidden="true" className="size-4 text-cyan-300" />
              {point}
            </li>
          ))}
        </ul>
        <nav aria-label={t("currency")} className="mt-2 flex gap-1 rounded-xl border border-border bg-surface p-1 text-sm text-foreground shadow-sm">
          {CURRENCIES.map((code) => (
            <Link
              key={code}
              href={`/pricing?currency=${code}`}
              aria-current={code === currency ? "page" : undefined}
              className={`rounded-lg px-3 py-1 font-medium ${code === currency ? "bg-primary text-on-primary" : "hover:bg-foreground/5"}`}
            >
              {code}
            </Link>
          ))}
        </nav>
      </PageHero>

      {catalog && (
        <>
          <Section aria-label={t("presetsTitle")} innerClassName="swipe gap-6 sm:grid md:grid-cols-3">
            {PRESETS.map((preset) => {
              const popular = preset === "growing";
              return (
                <article key={preset} className={`relative flex flex-col gap-5 p-7 ${popular ? "card-accent shadow-xl md:-translate-y-2" : "card"}`}>
                  {popular && <p className="absolute -top-3 start-6 rounded-full bg-primary px-3 py-1 text-xs font-bold text-on-primary shadow">{t("popular")}</p>}
                  <h2 className="text-xl font-bold">{t(`presets.${preset}`)}</h2>
                  <p className="text-sm text-muted">{t(`presetText.${preset}`)}</p>
                  <p className="flex items-baseline gap-1">
                    <span className="text-sm text-muted">{t("from")}</span>
                    <span className="text-4xl font-extrabold tracking-tight">
                      <bdi>{money(presetPrice(preset))}</bdi>
                    </span>
                    <span className="text-sm text-muted">{t("perMonth")}</span>
                  </p>
                  <ul className="flex flex-col gap-2 text-sm">
                    <li className="flex items-start gap-2">
                      <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success" />
                      {t("coreText")}
                    </li>
                    {(catalog.presets[preset] ?? []).map((key) => (
                      <li key={key} className="flex items-start gap-2">
                        <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success" />
                        {tModules(`names.${key}` as "names.client_app")}
                      </li>
                    ))}
                  </ul>
                  <Link href={`/start?preset=${preset}&currency=${currency}`} className={`mt-auto rounded-full px-5 py-3 text-center ${popular ? "btn-primary" : "btn-secondary"}`}>
                    {t("cta")}
                  </Link>
                  <p className="text-center text-xs text-muted">{t("trialNote")}</p>
                </article>
              );
            })}
          </Section>

          <Section tone="muted" aria-labelledby="tiers-heading" innerClassName="flex flex-col gap-8">
            <SectionHeading id="tiers-heading" title={t("core")} subtitle={t("coreText")} />
            <ul className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {catalog.core.map((tier) => (
                <li key={tier.up_to_clients ?? "custom"} className="card flex flex-col gap-1 p-5">
                  <span className="text-sm text-muted">{tier.up_to_clients ? t("upTo", { count: tier.up_to_clients }) : t("custom")}</span>
                  <span className="text-2xl font-extrabold">
                    {tier.up_to_clients ? (
                      <>
                        <bdi>{money(tier.price)}</bdi> <span className="text-sm font-medium text-muted">{t("perMonth")}</span>
                      </>
                    ) : (
                      t("customPrice")
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </Section>

          <Section size="default" aria-labelledby="compare-heading" innerClassName="flex flex-col gap-8">
            <SectionHeading id="compare-heading" title={t("compareTitle")} subtitle={t("compareText")} />
            <div className="card overflow-x-auto">
              <table className="w-full min-w-[34rem] text-sm">
                <caption className="sr-only">{t("compareTitle")}</caption>
                <thead>
                  <tr className="border-b border-border text-start">
                    <td />
                    {PRESETS.map((preset) => (
                      <th key={preset} scope="col" className={`px-4 py-4 text-center ${preset === "growing" ? "bg-primary/5" : ""}`}>
                        <span className="block font-bold">{t(`presets.${preset}`)}</span>
                        <span className="block text-lg font-extrabold">
                          <bdi>{money(presetPrice(preset))}</bdi>
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {["core", ...compared].map((key) => (
                    <tr key={key} className="border-b border-border last:border-0">
                      <th scope="row" className="px-4 py-3 text-start font-medium">
                        {key === "core" ? t("coreShort") : tModules(`names.${key}` as "names.client_app")}
                      </th>
                      {PRESETS.map((preset) => {
                        const has = key === "core" || (catalog.presets[preset] ?? []).includes(key as never);
                        return (
                          <td key={preset} className={`px-4 py-3 text-center ${preset === "growing" ? "bg-primary/5" : ""}`}>
                            {has ? <Check aria-label={t("included")} className="mx-auto size-5 text-success" /> : <Minus aria-label={t("notIncluded")} className="mx-auto size-4 text-muted" />}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          <Section tone="muted" aria-labelledby="calc-heading" innerClassName="flex flex-col gap-8">
            <SectionHeading id="calc-heading" title={t("calc.title")} subtitle={t("calc.subtitle")} />
            <PricingCalculator catalog={catalog} />
          </Section>

          <Section aria-labelledby="modules-heading" innerClassName="flex flex-col gap-8">
            <SectionHeading id="modules-heading" title={t("modulesTitle")} subtitle={t("modulesText")} />
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
              {[...catalog.modules].sort((x, y) => Number(y.available) - Number(x.available)).map((module) => (
                <li
                  key={module.key}
                  className={`card group grid grid-cols-[auto_1fr] items-start gap-x-4 gap-y-1 p-4 transition-[transform,box-shadow] sm:flex sm:flex-col sm:gap-3 sm:p-5 duration-300 hover:-translate-y-0.5 hover:shadow-lg ${
                    module.available ? "" : "opacity-80"
                  }`}
                >
                  <div className="row-span-3 flex flex-col items-start gap-2 sm:row-span-1 sm:flex-row sm:justify-between sm:gap-3">
                    <ModuleIcon module={module.key} />
                    {!module.available && (
                      <span className="rounded-full bg-foreground/8 px-2.5 py-1 text-xs font-semibold text-muted">{tModules("comingSoon")}</span>
                    )}
                  </div>
                  <h3 className="font-bold sm:text-lg">{tModules(`names.${module.key}` as "names.client_app")}</h3>
                  <p className="flex-1 text-sm text-muted">
                    {module.key === "extra_location"
                      ? tModules("descriptions.extra_location", { price: money(module.price) })
                      : tModules(`descriptions.${module.key}` as "descriptions.client_app")}
                  </p>
                  <p className="flex items-baseline gap-1 sm:border-t sm:border-border sm:pt-3">
                    <span className="text-lg font-extrabold sm:text-2xl">
                      + <bdi>{money(module.price)}</bdi>
                    </span>
                    <span className="text-sm text-muted">{module.billing === "once" ? t("oneTime") : t("perMonth")}</span>
                  </p>
                </li>
              ))}
            </ul>
          </Section>

          <Container as="p" className="pb-10 text-center text-sm text-muted">{t("note")}</Container>
        </>
      )}
      <Faq />
      <CtaBand />
    </main>
  );
}
