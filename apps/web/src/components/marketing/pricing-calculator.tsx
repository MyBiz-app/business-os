"use client";

import { Minus, Plus } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { ModuleIcon } from "@/components/modules/module-icon";
import type { Catalog } from "@/lib/pricing";
import { formatMoney } from "@/lib/money";
import {
  chooseTier,
  CLIENT_SIZES,
  type Modules,
  OFFER_TIERS,
  type Offer,
  priceLines,
  tierOf,
  tierPrice,
  withLocations,
} from "@/lib/signup-plan";

/** The add-ons a visitor can try out here (the same ones the sign-up journey offers). */
const OFFERS: Offer[] = ["client_app", "ai", "crm", "whatsapp"];

/** "What will I pay?": pick the business size and the add-ons and see the monthly total move.
 * Prices come from the catalog; nothing is saved. The button carries the currency to /start. */
export function PricingCalculator({ catalog }: { catalog: Catalog }) {
  const t = useTranslations("marketing.pricing.calc");
  const tp = useTranslations("marketing.pricing");
  const tModules = useTranslations("modules");
  const th = useTranslations("marketing.home.pricing");
  const locale = useLocale();
  const [clients, setClients] = useState<number>(100);
  const [locations, setLocations] = useState(1);
  const [chosen, setChosen] = useState<Modules>({});
  const money = (amount: number) => formatMoney(amount, catalog.currency, locale);
  const modules = withLocations(chosen, locations);
  const { total } = priceLines(catalog, { clients, modules });
  const sizeLabel = (size: number) => (size === 1500 ? tp("custom") : tp("upTo", { count: size.toLocaleString(locale) }));

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <div className="card flex flex-col gap-7 p-6 sm:p-8">
        <fieldset className="flex flex-col gap-3">
          <legend className="font-bold">{t("size")}</legend>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {CLIENT_SIZES.map((size) => (
              <button
                key={size}
                type="button"
                aria-pressed={size === clients}
                onClick={() => setClients(size)}
                className={`rounded-xl border px-3 py-3 text-sm font-semibold transition-colors ${
                  size === clients ? "border-primary bg-primary/10 text-primary ring-1 ring-primary" : "border-border hover:bg-foreground/5"
                }`}
              >
                {sizeLabel(size)}
              </button>
            ))}
          </div>
        </fieldset>

        <ul className="flex flex-col divide-y divide-border">
          {OFFERS.map((offer) => {
            const current = tierOf(offer, modules);
            const tiers = OFFER_TIERS[offer];
            const options = [{ key: null as string | null, label: t("none") }, ...tiers.map((tier) => ({ key: tier.key as string | null, label: tModules(`names.${tier.modules.at(-1)}` as "names.client_app") }))];
            return (
              <li key={offer} className="flex flex-col gap-3 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between">
                <span className="flex items-center gap-3 font-semibold">
                  <ModuleIcon module={tiers[0].modules[0]} size="sm" />
                  {tModules(`names.${tiers[0].modules[0]}` as "names.client_app")}
                </span>
                <div role="group" aria-label={tModules(`names.${tiers[0].modules[0]}` as "names.client_app")} className="flex flex-wrap gap-2">
                  {options.map((option) => {
                    const pressed = option.key === current;
                    return (
                      <button
                        key={option.key ?? "none"}
                        type="button"
                        aria-pressed={pressed}
                        onClick={() => setChosen((prev) => chooseTier(offer, option.key, prev, catalog))}
                        className={`rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors ${
                          pressed ? "border-primary bg-primary text-on-primary" : "border-border hover:bg-foreground/5"
                        }`}
                      >
                        {option.label}
                        {option.key && (
                          <span className="ms-1.5 opacity-80">
                            <bdi>+{money(tierPrice(offer, option.key, catalog))}</bdi>
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </li>
            );
          })}
          <li className="flex items-center justify-between gap-3 pt-4">
            <span className="font-semibold">{t("locations")}</span>
            <span className="flex items-center gap-3">
              <button type="button" aria-label={t("fewer")} disabled={locations <= 1} onClick={() => setLocations((n) => Math.max(1, n - 1))} className="btn-secondary size-9 disabled:opacity-40">
                <Minus aria-hidden="true" className="size-4" />
              </button>
              <output className="min-w-6 text-center font-bold tabular-nums">{locations}</output>
              <button type="button" aria-label={t("more")} disabled={locations >= 10} onClick={() => setLocations((n) => Math.min(10, n + 1))} className="btn-secondary size-9 disabled:opacity-40">
                <Plus aria-hidden="true" className="size-4" />
              </button>
            </span>
          </li>
        </ul>
      </div>

      <aside aria-live="polite" className="card-accent flex flex-col gap-4 self-start p-6 lg:sticky lg:top-24">
        <p className="text-sm font-semibold text-primary">{t("total")}</p>
        <p className="flex items-baseline gap-1">
          <span className="text-5xl font-extrabold tracking-tight">
            <bdi>{money(total)}</bdi>
          </span>
          <span className="text-muted">{tp("perMonth")}</span>
        </p>
        <p className="text-sm text-muted">{t("daily", { price: money(Math.ceil(total / 30)) })}</p>
        <ul className="flex flex-col gap-1 text-sm font-medium">
          {(th.raw("points") as string[]).slice(0, 3).map((point) => (
            <li key={point}>✓ {point}</li>
          ))}
        </ul>
        <Link href={`/start?currency=${catalog.currency}`} className="btn-primary rounded-full px-5 py-3 text-center">
          {tp("cta")}
        </Link>
      </aside>
    </div>
  );
}
