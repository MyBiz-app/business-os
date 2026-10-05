import type { components } from "@business-os/api-client";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { ChatMock, PhoneMock } from "@/components/marketing/mocks";
import { API_URL } from "@/lib/api";
import { CURRENCIES, type Currency, trialEndsOn, VERTICALS, type Vertical, withLocations } from "@/lib/signup-plan";

import { StartWizard } from "./start-wizard";

type Catalog = components["schemas"]["Catalog"];

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("start.meta");
  return { title: `${t("title")} · MyBiz`, description: t("description") };
}

async function loadCatalog(currency: Currency): Promise<Catalog | null> {
  try {
    const response = await fetch(`${API_URL}/public/pricing?currency=${currency}`, { next: { revalidate: 3600 } });
    return response.ok ? ((await response.json()) as Catalog) : null;
  } catch {
    return null;
  }
}

/** "Start free": the sign-up journey. Links can preselect an industry (?vertical=beauty), a
 * recommended plan (?preset=growing) or a currency (?currency=USD). */
export default async function StartPage({ searchParams }: PageProps<"/start">) {
  const t = await getTranslations("start");
  const tMarketing = await getTranslations("marketing");
  const locale = await getLocale();
  const query = await searchParams;
  const catalogs: Partial<Record<Currency, Catalog>> = {};
  for (const [currency, catalog] of await Promise.all(CURRENCIES.map(async (c) => [c, await loadCatalog(c)] as const))) {
    if (catalog) catalogs[currency] = catalog;
  }

  if (Object.keys(catalogs).length === 0) {
    return (
      <main className="enter mx-auto flex max-w-xl flex-col items-center gap-4 px-6 py-24 text-center">
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
  const vertical = asked<Vertical>(query.vertical, VERTICALS);
  const requestedCurrency = asked<Currency>(query.currency, CURRENCIES);
  const currency = requestedCurrency && catalogs[requestedCurrency] ? requestedCurrency : locale === "he" && catalogs.ILS ? "ILS" : (Object.keys(catalogs)[0] as Currency);
  const preset = typeof query.preset === "string" ? query.preset : "";
  const presetModules = Object.values(catalogs)[0]!.presets[preset] ?? [];

  return (
    <main className="flex flex-col">
      <StartWizard
        catalogs={catalogs}
        initial={{
          vertical,
          name: "",
          clients: 100,
          staff: 2,
          locations: 1,
          currency,
          modules: withLocations(Object.fromEntries(presetModules.map((key) => [key, 1])), 1),
        }}
        trialEndsOn={trialEndsOn()}
        illustrations={{
          client_app: <PhoneMock />,
          ai: <ChatMock question={t("offers.ai.question")} answer={t("offers.ai.answer")} />,
        }}
      />
    </main>
  );
}
