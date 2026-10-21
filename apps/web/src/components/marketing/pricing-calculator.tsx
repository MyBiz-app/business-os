"use client";

import { vertical as findVertical } from "@business-os/verticals";
import { Minus, Plus } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import type { Catalog } from "@/lib/pricing";
import { formatMoney } from "@/lib/money";
import {
  calcPlanQuery,
  chooseTier,
  CLIENT_SIZES,
  clientsTier,
  type Currency,
  type Modules,
  type Offer,
  priceLines,
  tierOf,
  withLocations,
} from "@/lib/signup-plan";

import { CalcAddonCard } from "./calc-addon-card";
import { CalcIndustry } from "./calc-industry";
import { CalcReceipt } from "./calc-receipt";
import { CollapsibleSection } from "@/components/ui/collapsible-section";

/** The add-ons a visitor can try out here (the same ones the sign-up journey offers). */
const OFFERS: Offer[] = ["client_app", "ai", "crm", "whatsapp"];
/** The slider's top end stands for "1,000+" (the last core tier). */
const MAX_CLIENTS = 1500;
/** What the visitor may enter that they pay today (only their own numbers are ever shown). */
const TODAY_ROWS = ["scheduling", "clientApp", "whatsapp", "crm", "other"] as const;

/** "What will I pay?": the kind of business, the number of active clients, the branches and the
 * add-ons, with a live receipt. Prices come from the catalog; nothing is saved. The button sends
 * the whole plan to /start. `compact` is the home page's short version (business, clients, total). */
export function PricingCalculator({ catalog, compact = false }: { catalog: Catalog; compact?: boolean }) {
  const t = useTranslations("marketing.pricing.calc");
  const tp = useTranslations("marketing.pricing");
  const locale = useLocale();
  const [industry, setIndustry] = useState<string | null>(null);
  const [clients, setClients] = useState<number>(100);
  const [locations, setLocations] = useState(1);
  const [chosen, setChosen] = useState<Modules>({});
  const [today, setToday] = useState<Record<string, string>>({});
  const [sheet, setSheet] = useState(false);
  const money = (amount: number) => formatMoney(amount, catalog.currency, locale);
  const modules = withLocations(chosen, locations);
  const { lines, total, once, onceTotal } = priceLines(catalog, { clients, modules });
  const tier = clientsTier(clients);
  const tierName = tier === 1500 ? tp("custom") : tp("upTo", { count: tier.toLocaleString(locale) });
  const recommends = findVertical(industry)?.recommendedModules ?? [];
  const clientsText = clients >= MAX_CLIENTS ? "1,000+" : clients.toLocaleString(locale);
  const href = `/start?${calcPlanQuery({ vertical: industry, clients, locations, currency: catalog.currency as Currency, modules })}`;

  const todayTotal = TODAY_ROWS.reduce((sum, row) => sum + Math.round((Number(today[row]) || 0) * 100), 0);

  const slider = (
    <div className="flex flex-col gap-3">
      <label htmlFor="calc-clients" className="font-bold">
        <span aria-hidden="true" className="me-2 text-primary-ink">②</span>
        {t("size")}
      </label>
      <input
        id="calc-clients"
        type="range"
        min={0}
        max={MAX_CLIENTS}
        step={10}
        value={clients}
        onChange={(event) => setClients(Number(event.target.value))}
        aria-valuetext={t("sliderValue", { clients: clientsText, tier: tierName })}
        className="w-full accent-primary"
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted" aria-hidden="true">
          {t("sliderValue", { clients: clientsText, tier: tierName })}
        </p>
        <label className="flex items-center gap-2 text-sm">
          <span className="sr-only">{t("sizeNumber")}</span>
          <input
            type="number"
            inputMode="numeric"
            min={0}
            max={100000}
            value={clients}
            onChange={(event) => setClients(Math.min(100_000, Math.max(0, Math.trunc(Number(event.target.value)) || 0)))}
            className="w-24 rounded-lg border border-border bg-background px-2 py-1.5 text-center tabular-nums"
          />
        </label>
      </div>
      <div className="flex flex-wrap gap-1.5 text-xs text-muted" aria-hidden="true">
        {CLIENT_SIZES.map((size) => (
          <span key={size} className={`rounded-full border px-2 py-0.5 ${size === tier ? "border-primary text-primary-ink" : "border-border"}`}>
            {size === 1500 ? tp("custom") : tp("upTo", { count: size.toLocaleString(locale) })}
          </span>
        ))}
      </div>
    </div>
  );

  if (compact) {
    return (
      <div className="card mx-auto flex w-full max-w-3xl flex-col gap-6 p-6 sm:p-8">
        <CalcIndustry value={industry} onChange={setIndustry} />
        {slider}
        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-5">
          <p aria-live="polite" className="flex items-baseline gap-1">
            <span className="text-4xl font-extrabold tracking-tight tabular-nums">
              <bdi>{money(total)}</bdi>
            </span>
            <span className="text-muted">{tp("perMonth")}</span>
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/pricing#calculator" className="btn-secondary rounded-full px-5 py-3">
              {t("fullCalc")}
            </Link>
            <Link href={href} className="btn-primary rounded-full px-5 py-3">
              {t("startWithThis")}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const receipt = (
    <CalcReceipt catalog={catalog} locale={locale} lines={lines} once={once} total={total} onceTotal={onceTotal} clients={clients >= MAX_CLIENTS ? 0 : clients} tierName={tierName} />
  );

  return (
    <div id="calculator" className="grid gap-6 pb-20 lg:grid-cols-[1fr_22rem] lg:pb-0">
      <div className="card flex flex-col gap-8 p-6 sm:p-8">
        <CalcIndustry value={industry} onChange={setIndustry} />
        {slider}

        <div className="flex items-center justify-between gap-3">
          <span className="font-bold">
            <span aria-hidden="true" className="me-2 text-primary-ink">③</span>
            {t("locations")}
          </span>
          <span className="flex items-center gap-3">
            <button type="button" aria-label={t("fewer")} disabled={locations <= 1} onClick={() => setLocations((n) => Math.max(1, n - 1))} className="btn-secondary size-9 disabled:opacity-40">
              <Minus aria-hidden="true" className="size-4" />
            </button>
            <output className="min-w-6 text-center font-bold tabular-nums">{locations}</output>
            <button type="button" aria-label={t("more")} disabled={locations >= 10} onClick={() => setLocations((n) => Math.min(10, n + 1))} className="btn-secondary size-9 disabled:opacity-40">
              <Plus aria-hidden="true" className="size-4" />
            </button>
          </span>
        </div>

        <div className="flex flex-col gap-3">
          <p className="font-bold">
            <span aria-hidden="true" className="me-2 text-primary-ink">④</span>
            {t("addons")}
          </p>
          <ul className="grid gap-3 sm:grid-cols-2">
            {OFFERS.map((offer) => (
              <CalcAddonCard
                key={offer}
                offer={offer}
                tier={tierOf(offer, modules)}
                catalog={catalog}
                locale={locale}
                recommended={recommends.includes(offer)}
                onChange={(next) => setChosen((prev) => chooseTier(offer, next, prev, catalog))}
              />
            ))}
          </ul>
        </div>

        <CollapsibleSection variant="inline" className="rounded-xl border border-border p-4" triggerClassName="font-semibold text-primary-ink" title={t("todayTitle")}>
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted">{t("todayHint")}</p>
            {TODAY_ROWS.map((row) => (
              <label key={row} className="flex items-center justify-between gap-3 text-sm">
                <span>{t(`today.${row}` as "today.other")}</span>
                <input
                  type="number"
                  inputMode="decimal"
                  min={0}
                  value={today[row] ?? ""}
                  onChange={(event) => setToday((prev) => ({ ...prev, [row]: event.target.value }))}
                  className="w-28 rounded-lg border border-border bg-background px-2 py-1.5 text-center tabular-nums"
                />
              </label>
            ))}
            {todayTotal > 0 && (
              <p aria-live="polite" className="rounded-lg bg-foreground/5 p-3 text-sm font-semibold">
                {t("todayCompare", { today: money(todayTotal), total: money(total) })}
                <span className="mt-1 block font-normal text-muted">
                  {total <= todayTotal ? t("todaySave", { amount: money(todayTotal - total) }) : t("todayMore", { amount: money(total - todayTotal) })}
                </span>
              </p>
            )}
          </div>
        </CollapsibleSection>
      </div>

      <aside aria-live="polite" className="card-accent hidden flex-col gap-4 self-start p-6 lg:sticky lg:top-24 lg:flex">
        {receipt}
        <Link href={href} className="btn-primary rounded-full px-5 py-3 text-center">
          {t("startWithThis")}
        </Link>
      </aside>

      {/* Phones: the receipt becomes a bar at the bottom of the screen that opens as a sheet. */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-background shadow-lg lg:hidden">
        {sheet && (
          <div id="calc-sheet" className="max-h-[60vh] overflow-y-auto border-b border-border p-5">
            {receipt}
          </div>
        )}
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <button type="button" aria-expanded={sheet} aria-controls="calc-sheet" onClick={() => setSheet((open) => !open)} className="btn-plain flex flex-col text-start">
            <span className="text-xl font-extrabold tabular-nums">
              <bdi>{money(total)}</bdi>
              <span className="ms-1 text-sm font-normal text-muted">{tp("perMonth")}</span>
            </span>
            <span className="text-xs font-semibold text-primary-ink">{sheet ? t("hideDetails") : t("showDetails")}</span>
          </button>
          <Link href={href} className="btn-primary rounded-full px-5 py-2.5">
            {t("startWithThis")}
          </Link>
        </div>
      </div>
    </div>
  );
}
