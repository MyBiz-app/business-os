"use client";

import type { components } from "@business-os/api-client";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { formatMoney } from "@/lib/money";

export type Catalog = components["schemas"]["Catalog"];
type ModuleKey = components["schemas"]["CatalogModule"]["key"];
export type Selection = Partial<Record<ModuleKey, number>>;

/** Modules sold as tiers of one thing: a choice of one (or none) instead of toggles. */
const GROUPS = [
  { key: "ai", legend: "aiTier", none: "none", tiers: ["ai_basic", "ai_pro"] },
  { key: "support", legend: "supportTier", none: "noSupport", tiers: ["support_priority", "support_vip"] },
  { key: "pack", legend: "packTier", none: "noPack", tiers: ["pack_plus", "pack_max"] },
] as const;

type Props = {
  catalog: Catalog;
  initial: Selection;
  activeClients: number;
  /** Name of the hidden input that carries the selection (JSON) in the form. */
  name: string;
  /** For an existing business, extra branches follow its active branches: shown, not chosen. */
  branchesFollowLocations?: boolean;
};

/** Toggles for the business's modules with a live monthly price. The server validates and
 * prices the selection again when it is saved; this is the preview. */
export function ModulePicker({ catalog, initial, activeClients, name, branchesFollowLocations = false }: Props) {
  const t = useTranslations("modules");
  const locale = useLocale();
  const [selection, setSelection] = useState<Selection>(initial);
  const money = (amount: number) => formatMoney(amount, catalog.currency, locale);
  const byKey = Object.fromEntries(catalog.modules.map((m) => [m.key, m]));
  const core = catalog.core.find((tier) => tier.up_to_clients === null || activeClients <= tier.up_to_clients)!;
  // One-time services (setup) were bought once and are not part of the monthly price.
  const total =
    core.price +
    Object.entries(selection).reduce((sum, [key, quantity]) => sum + (byKey[key]?.billing === "once" ? 0 : (byKey[key]?.price ?? 0) * (quantity ?? 0)), 0);

  const set = (key: ModuleKey, quantity: number) =>
    setSelection((current) => {
      const next = { ...current };
      if (quantity > 0) next[key] = quantity;
      else delete next[key];
      return next;
    });
  const setTier = (tiers: readonly ModuleKey[], tier: ModuleKey | null) =>
    setSelection((current) => {
      const next = { ...current };
      for (const key of tiers) delete next[key];
      if (tier) next[tier] = 1;
      return next;
    });

  // On/off modules; tiers and per-unit locations have their own controls, and one-time
  // services are not changed here.
  const special = (key: string) => key === "extra_location" || !!byKey[key]?.group || byKey[key]?.billing === "once";
  const toggles = catalog.modules.filter((m) => m.available && !special(m.key));
  const others = catalog.modules.filter((m) => !m.available && !special(m.key));

  return (
    <div className="flex flex-col gap-5">
      <input type="hidden" name={name} value={JSON.stringify(selection)} />

      <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-background p-4">
        <div className="flex flex-col">
          <span className="font-semibold">{t("core")}</span>
          <span className="text-sm text-muted">
            {core.up_to_clients === null ? t("coreTierCustom") : t("coreTier", { count: core.up_to_clients })}
          </span>
        </div>
        <span className="font-semibold">{money(core.price)}</span>
      </div>

      {toggles.map((module) => (
        <label key={module.key} className="flex items-center justify-between gap-3 rounded-xl border border-border bg-background p-4">
          <span className="flex items-start gap-3">
            <input
              type="checkbox"
              className="mt-1 size-4 accent-[var(--primary)]"
              checked={!!selection[module.key]}
              onChange={(event) => set(module.key, event.target.checked ? 1 : 0)}
            />
            <span className="flex flex-col">
              <span className="font-semibold">{t(`names.${module.key}`)}</span>
              <span className="text-sm text-muted">{t(`descriptions.${module.key as "client_app"}`)}</span>
            </span>
          </span>
          <span className="shrink-0 text-sm">{money(module.price)}</span>
        </label>
      ))}

      {GROUPS.map((group) => {
        const chosen = group.tiers.find((tier) => selection[tier]) ?? null;
        return (
          <fieldset key={group.key} className="flex flex-col gap-2 rounded-xl border border-border bg-background p-4">
            <legend className="px-1 font-semibold">{t(group.legend)}</legend>
            {[null, ...group.tiers].map((tier) => (
              <label key={tier ?? "none"} className="flex items-center justify-between gap-3">
                <span className="flex items-start gap-3">
                  <input
                    type="radio"
                    name={`${name}-${group.key}`}
                    className="mt-1 size-4 accent-[var(--primary)]"
                    checked={chosen === tier}
                    onChange={() => setTier(group.tiers, tier)}
                  />
                  <span className="flex flex-col">
                    <span className="font-medium">{t(`names.${tier ?? group.none}`)}</span>
                    <span className="text-sm text-muted">{t(`descriptions.${tier ?? group.none}`)}</span>
                  </span>
                </span>
                {tier && <span className="shrink-0 text-sm">{money(byKey[tier].price)}</span>}
              </label>
            ))}
          </fieldset>
        );
      })}

      <label className="flex items-center justify-between gap-3 rounded-xl border border-border bg-background p-4">
        <span className="flex flex-col">
          <span className="font-semibold">{t("names.extra_location")}</span>
          <span className="text-sm text-muted">{t("descriptions.extra_location", { price: money(byKey.extra_location.price) })}</span>
        </span>
        {branchesFollowLocations ? (
          <span className="flex flex-col items-end gap-0.5 text-end">
            <span className="text-lg font-bold tabular-nums">{selection.extra_location ?? 0}</span>
            <span className="text-xs text-muted">{t("followsBranches")}</span>
          </span>
        ) : (
          <input
            type="number"
            min={0}
            max={50}
            value={selection.extra_location ?? 0}
            onChange={(event) => set("extra_location", Math.max(0, Math.min(50, Number(event.target.value) || 0)))}
            aria-label={t("names.extra_location")}
            className="control w-20 px-2 py-1.5 text-center"
          />
        )}
      </label>

      <ul className="grid gap-2 sm:grid-cols-2">
        {others.map((module) => (
          <li key={module.key} className="flex items-center justify-between gap-2 rounded-xl border border-dashed border-border p-3 text-sm text-muted">
            <span>{t(`names.${module.key}`)}</span>
            <span>{t("comingSoon")}</span>
          </li>
        ))}
      </ul>

      <div className="flex items-baseline justify-between gap-3 border-t border-border pt-4" aria-live="polite">
        <span className="font-semibold">{t("monthlyTotal")}</span>
        <span className="text-2xl font-bold">{money(total)}</span>
      </div>
      <p className="text-xs text-muted">{t("placeholderPrices")}</p>
    </div>
  );
}
