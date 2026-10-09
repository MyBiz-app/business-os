import type { components } from "@business-os/api-client";
import { Check } from "lucide-react";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { CtaBand, Faq } from "@/components/marketing/sections";
import { FaqData, OrganizationData } from "@/components/marketing/structured-data";
import { ModuleIcon } from "@/components/modules/module-icon";
import { API_URL } from "@/lib/api";
import { formatMoney, toMajor } from "@/lib/money";

type Catalog = components["schemas"]["Catalog"];

const CURRENCIES = ["ILS", "USD", "EUR"] as const;
const PRESETS = ["starter", "growing", "ai_powered"] as const;

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.meta");
  return { title: `${t("pricing")} · ${BRAND.name}` };
}

async function loadCatalog(currency: string): Promise<Catalog | null> {
  try {
    const response = await fetch(`${API_URL}/public/pricing?currency=${currency}`, { next: { revalidate: 3600 } });
    return response.ok ? ((await response.json()) as Catalog) : null;
  } catch {
    return null;
  }
}

/** Prices from the API's module catalog: recommended plans, base tiers and every module. */
export default async function PricingPage({ searchParams }: PageProps<"/pricing">) {
  const t = await getTranslations("marketing.pricing");
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

  return (
    <main className="enter flex flex-col">
      {/* The starting price is the base tier, the same number the cards show. */}
      <OrganizationData price={toMajor(base, currency)} currency={currency} />
      <FaqData />
      <section className="mx-auto flex max-w-3xl flex-col items-center gap-4 px-6 pt-16 text-center">
        <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">{t("title")}</h1>
        <p className="text-lg text-muted">{t("subtitle")}</p>
        <nav aria-label={t("currency")} className="flex gap-1 rounded-xl border border-border bg-surface p-1 text-sm shadow-sm">
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
      </section>

      {catalog && (
        <>
          <section aria-label={t("presetsTitle")} className="mx-auto grid w-full max-w-6xl gap-5 px-6 py-12 md:grid-cols-3">
            {PRESETS.map((preset) => {
              const popular = preset === "growing";
              return (
                <article
                  key={preset}
                  className={`relative flex flex-col gap-5 p-7 ${popular ? "card-accent shadow-xl md:-translate-y-2" : "card"}`}
                >
                  {popular && (
                    <p className="absolute -top-3 start-6 rounded-full bg-primary px-3 py-1 text-xs font-bold text-on-primary shadow">
                      {t("popular")}
                    </p>
                  )}
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
                  <Link href={`/start?preset=${preset}&currency=${currency}`} className={`mt-auto px-5 py-3 ${popular ? "btn-primary" : "btn-secondary"}`}>
                    {t("cta")}
                  </Link>
                </article>
              );
            })}
          </section>

          <section aria-labelledby="tiers-heading" className="mx-auto w-full max-w-6xl px-6 pb-12">
            <div className="card-accent flex flex-col gap-5 p-6 sm:p-8">
              <div className="flex flex-col gap-1">
                <h2 id="tiers-heading" className="text-2xl font-extrabold tracking-tight">
                  {t("core")}
                </h2>
                <p className="text-muted">{t("coreText")}</p>
              </div>
              <ul className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                {catalog.core.map((tier) => (
                  <li key={tier.up_to_clients ?? "custom"} className="flex flex-col gap-1 rounded-2xl border border-border bg-surface p-4">
                    <span className="text-sm text-muted">{tier.up_to_clients ? t("upTo", { count: tier.up_to_clients }) : t("custom")}</span>
                    <span className="text-xl font-extrabold">
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
            </div>
          </section>
          <section aria-labelledby="modules-heading" className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 pb-12">
            <div className="flex flex-col gap-2 text-center">
              <h2 id="modules-heading" className="text-3xl font-extrabold tracking-tight">
                {t("modulesTitle")}
              </h2>
              <p className="text-muted">{t("modulesText")}</p>
            </div>
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[...catalog.modules].sort((x, y) => Number(y.available) - Number(x.available)).map((module) => (
                <li
                  key={module.key}
                  className={`card group flex flex-col gap-3 p-5 transition-[transform,box-shadow] duration-300 hover:-translate-y-0.5 hover:shadow-lg ${
                    module.available ? "" : "opacity-80"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <ModuleIcon module={module.key} />
                    {!module.available && (
                      <span className="rounded-full bg-foreground/8 px-2.5 py-1 text-xs font-semibold text-muted">{tModules("comingSoon")}</span>
                    )}
                  </div>
                  <h3 className="text-lg font-bold">{tModules(`names.${module.key}` as "names.client_app")}</h3>
                  <p className="flex-1 text-sm text-muted">
                    {module.key === "extra_location"
                      ? tModules("descriptions.extra_location", { price: money(module.price) })
                      : tModules(`descriptions.${module.key}` as "descriptions.client_app")}
                  </p>
                  <p className="flex items-baseline gap-1 border-t border-border pt-3">
                    <span className="text-2xl font-extrabold">
                      + <bdi>{money(module.price)}</bdi>
                    </span>
                    <span className="text-sm text-muted">{module.billing === "once" ? t("oneTime") : t("perMonth")}</span>
                  </p>
                </li>
              ))}
            </ul>
          </section>

          <p className="px-6 text-center text-sm text-muted">{t("note")}</p>
        </>
      )}
      <Faq />
      <CtaBand />
    </main>
  );
}
