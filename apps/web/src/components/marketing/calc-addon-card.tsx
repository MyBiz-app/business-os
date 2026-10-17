"use client";

import { Check } from "lucide-react";
import { useTranslations } from "next-intl";

import { ModuleIcon } from "@/components/modules/module-icon";
import type { Catalog } from "@/lib/pricing";
import { formatMoney } from "@/lib/money";
import { OFFER_TIERS, type Offer, tierPrice } from "@/lib/signup-plan";

type Props = {
  offer: Offer;
  /** The chosen tier ("basic" / "pro"), or null when the add-on is off. */
  tier: string | null;
  catalog: Catalog;
  locale: string;
  recommended: boolean;
  onChange: (tier: string | null) => void;
};

/** One add-on as a card: what you get, the price, an on/off switch and (when on) its levels. */
export function CalcAddonCard({ offer, tier, catalog, locale, recommended, onChange }: Props) {
  const t = useTranslations("marketing.pricing.calc");
  const tModules = useTranslations("modules");
  const tiers = OFFER_TIERS[offer];
  const first = tiers[0];
  const on = tier !== null;
  const name = tModules(`names.${first.modules[0]}` as "names.client_app");
  const money = (key: string) => formatMoney(tierPrice(offer, key, catalog), catalog.currency, locale);
  return (
    <li className={`flex flex-col gap-3 rounded-2xl border p-4 transition-colors ${on ? "border-primary bg-primary/5 ring-1 ring-primary" : "border-border"}`}>
      <button type="button" aria-pressed={on} onClick={() => onChange(on ? null : first.key)} className="btn-plain flex items-start gap-3 text-start">
        <ModuleIcon module={first.modules[0]} size="sm" />
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="flex flex-wrap items-center gap-2 font-bold">
            {name}
            {recommended && <span className="rounded-full bg-success/15 px-2 py-0.5 text-xs font-semibold text-success-ink">{t("recommended")}</span>}
          </span>
          <span className="text-sm text-muted">{t(`offers.${offer}` as "offers.client_app")}</span>
        </span>
        <span aria-hidden="true" className={`flex size-6 shrink-0 items-center justify-center rounded-full border ${on ? "border-primary bg-primary text-on-primary" : "border-border"}`}>
          {on && <Check className="size-4" />}
        </span>
      </button>
      <p className="ps-11 text-sm font-semibold">
        <bdi>+{money(on ? tier : first.key)}</bdi>
        <span className="ms-1 font-normal text-muted">{t("perMonthShort")}</span>
      </p>
      {on && tiers.length > 1 && (
        <div role="group" aria-label={name} className="ms-11 inline-flex self-start rounded-full border border-border p-0.5">
          {tiers.map((option) => (
            <button
              key={option.key}
              type="button"
              aria-pressed={option.key === tier}
              onClick={() => onChange(option.key)}
              className={`btn-plain rounded-full px-3 py-1 text-sm font-medium transition-colors ${option.key === tier ? "bg-primary text-on-primary" : "hover:bg-foreground/5"}`}
            >
              {t(`tier.${option.key}` as "tier.basic")}
              <bdi className="ms-1 opacity-80">+{money(option.key)}</bdi>
            </button>
          ))}
        </div>
      )}
    </li>
  );
}
