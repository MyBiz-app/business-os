import type { components } from "@business-os/api-client";
import { isOpen } from "@business-os/verticals";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { ChatMock, PhoneMock } from "@/components/marketing/mocks";
import { API_URL } from "@/lib/api";
import { providerButtons } from "@/lib/auth-providers";
import { createClient } from "@/lib/supabase/server";
import { loadSitePrices } from "@/lib/pricing";
import { CURRENCIES, type Currency, modulesFromParam, type SiteFees, trialEndsOn, websiteFees, wholeParam, withLocations, withoutOrphans } from "@/lib/signup-plan";

import { SiteOnlyStart } from "./site-only";
import { StartWizard } from "./start-wizard";

type Catalog = components["schemas"]["Catalog"] & { website?: SiteFees };

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("start.meta");
  return { title: `${t("title")} · ${BRAND.name}`, description: t("description") };
}

async function loadCatalog(currency: Currency): Promise<Catalog | null> {
  try {
    const response = await fetch(`${API_URL}/public/pricing?currency=${currency}`, { next: { revalidate: 3600 } });
    return response.ok ? { ...((await response.json()) as Catalog), website: websiteFees(await loadSitePrices(currency)) } : null;
  } catch {
    return null;
  }
}

const asCurrency = (value: unknown): Currency | null => (CURRENCIES as readonly unknown[]).includes(value) ? (value as Currency) : null;

/** "Start free": the sign-up journey. Links can preselect an industry (?vertical=beauty or a sub-category such as barbershop), a
 * recommended plan (?preset=growing) or a currency (?currency=USD). */
export default async function StartPage({ searchParams }: PageProps<"/start">) {
  const t = await getTranslations("start");
  const tMarketing = await getTranslations("marketing");
  const locale = await getLocale();
  const query = await searchParams;
  // "Website only" from the /websites page: its own short sign-up, no price list needed.
  if (query.track === "site") {
    const { data: claims } = await (await createClient()).auth.getClaims();
    const wanted = asCurrency(query.currency);
    const siteCurrency = wanted ?? (locale === "he" ? "ILS" : "USD");
    return (
      <main id="main" className="flex flex-col">
        <SiteOnlyStart currency={siteCurrency} signedIn={Boolean(claims?.claims)} price={websiteFees(await loadSitePrices(siteCurrency))?.alone} />
      </main>
    );
  }
  const catalogs: Partial<Record<Currency, Catalog>> = {};
  for (const [currency, catalog] of await Promise.all(CURRENCIES.map(async (c) => [c, await loadCatalog(c)] as const))) {
    if (catalog) catalogs[currency] = catalog;
  }

  if (Object.keys(catalogs).length === 0) {
    return (
      <main id="main" className="enter mx-auto flex max-w-xl flex-col items-center gap-4 px-6 py-24 text-center">
        <h1 className="text-3xl font-bold">{t("meta.title")}</h1>
        <p className="text-muted">{t("finish.errors.generic")}</p>
        <Link href="/contact" className="btn-primary px-5 py-3">
          {tMarketing("nav.contact")}
        </Link>
      </main>
    );
  }

  const asked = <T extends string>(value: unknown, allowed: readonly T[]) =>
    typeof value === "string" && (allowed as readonly string[]).includes(value) ? (value as T) : null;
  const vertical = typeof query.vertical === "string" && isOpen(query.vertical) ? query.vertical : null;
  const requestedCurrency = asked<Currency>(query.currency, CURRENCIES);
  const currency = requestedCurrency && catalogs[requestedCurrency] ? requestedCurrency : locale === "he" && catalogs.ILS ? "ILS" : (Object.keys(catalogs)[0] as Currency);
  const fromCalc = query.from === "calc";
  const locations = fromCalc ? wholeParam(query.locations, 1, 11, 1) : 1;
  const preset = typeof query.preset === "string" ? query.preset : "";
  const presetModules = Object.values(catalogs)[0]!.presets[preset] ?? [];
  const { data: claims } = await (await createClient()).auth.getClaims();
  const signedIn = Boolean(claims?.claims);
  const search = new URLSearchParams(
    Object.entries(query).filter((entry): entry is [string, string] => typeof entry[1] === "string"),
  ).toString();

  return (
    <main id="main" className="flex flex-col">
      <StartWizard
        catalogs={catalogs}
        initial={{
          vertical,
          name: "",
          clients: fromCalc ? wholeParam(query.clients, 0, 100_000, 100) : 100,
          staff: 2,
          locations,
          currency,
          ...(query.site === "build" ? { site: "build" as const } : {}),
          modules: withLocations(fromCalc ? withoutOrphans(modulesFromParam(query.modules), catalogs[currency] ?? Object.values(catalogs)[0]!) : Object.fromEntries(presetModules.map((key) => [key, 1])), locations),
        }}
        fromCalc={fromCalc}
        trialEndsOn={trialEndsOn()}
        providers={signedIn ? [] : await providerButtons()}
        signedIn={signedIn}
        returnTo={search ? `/start?${search}` : "/start"}
        illustrations={{
          client_app: <PhoneMock />,
          ai: <ChatMock question={t("offers.ai.question")} answer={t("offers.ai.answer")} />,
        }}
      />
    </main>
  );
}
