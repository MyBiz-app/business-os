"use client";

import type { components } from "@business-os/api-client";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { formatMoney } from "@/lib/money";

export type Catalog = components["schemas"]["Catalog"];
type ModuleKey = components["schemas"]["CatalogModule"]["key"];
export type Selection = Partial<Record<ModuleKey, number>>;

const AI_TIERS = ["none", "ai_basic", "ai_pro"] as const;
type AiTier = (typeof AI_TIERS)[number];

type Props = {
  catalog: Catalog;
  initial: Selection;
  activeClients: number;
  /** Name of the hidden input that carries the selection (JSON) in the form. */
  name: string;
};

/** Toggles for the business's modules with a live monthly price. The server validates and
 * prices the selection again when it is saved; this is the preview. */
export function ModulePicker({ catalog, initial, activeClients, name }: Props) {
  const t = useTranslations("modules");
  const locale = useLocale();
  const [selection, setSelection] = useState<Selection>(initial);
  const money = (amount: number) => formatMoney(amount, catalog.currency, locale);
  const byKey = Object.fromEntries(catalog.modules.map((m) => [m.key, m]));
  const core = catalog.core.find((tier) => tier.up_to_clients === null || activeClients <= tier.up_to_clients)!;
  const aiTier: AiTier = selection.ai_pro ? "ai_pro" : selection.ai_basic ? "ai_basic" : "none";
  const total =
    core.price + Object.entries(selection).reduce((sum, [key, quantity]) => sum + byKey[key].price * (quantity ?? 0), 0);

  const set = (key: ModuleKey, quantity: number) =>
    setSelection((current) => {
      const next = { ...current };
      if (quantity > 0) next[key] = quantity;
      else delete next[key];
      return next;
    });
  const setAi = (tier: AiTier) =>
    setSelection((current) => {
      const next = { ...current };
      delete next.ai_basic;
      delete next.ai_pro;
      if (tier !== "none") next[tier] = 1;
      return next;
    });

  const others = catalog.modules.filter((m) => !["ai_basic", "ai_pro", "client_app", "extra_location"].includes(m.key));

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

      <label className="flex items-center justify-between gap-3 rounded-xl border border-border bg-background p-4">
        <span className="flex items-start gap-3">
          <input
            type="checkbox"
            className="mt-1 size-4 accent-[var(--primary)]"
            checked={!!selection.client_app}
            onChange={(event) => set("client_app", event.target.checked ? 1 : 0)}
          />
          <span className="flex flex-col">
            <span className="font-semibold">{t("names.client_app")}</span>
            <span className="text-sm text-muted">{t("descriptions.client_app")}</span>
          </span>
        </span>
        <span className="shrink-0 text-sm">{money(byKey.client_app.price)}</span>
      </label>

      <fieldset className="flex flex-col gap-2 rounded-xl border border-border bg-background p-4">
        <legend className="px-1 font-semibold">{t("aiTier")}</legend>
        {AI_TIERS.map((tier) => (
          <label key={tier} className="flex items-center justify-between gap-3">
            <span className="flex items-start gap-3">
              <input
                type="radio"
                name={`${name}-ai`}
                className="mt-1 size-4 accent-[var(--primary)]"
                checked={aiTier === tier}
                onChange={() => setAi(tier)}
              />
              <span className="flex flex-col">
                <span className="font-medium">{t(`names.${tier}`)}</span>
                <span className="text-sm text-muted">{t(`descriptions.${tier}`)}</span>
              </span>
            </span>
            {tier !== "none" && <span className="shrink-0 text-sm">{money(byKey[tier].price)}</span>}
          </label>
        ))}
      </fieldset>

      <label className="flex items-center justify-between gap-3 rounded-xl border border-border bg-background p-4">
        <span className="flex flex-col">
          <span className="font-semibold">{t("names.extra_location")}</span>
          <span className="text-sm text-muted">{t("descriptions.extra_location", { price: money(byKey.extra_location.price) })}</span>
        </span>
        <input
          type="number"
          min={0}
          max={50}
          value={selection.extra_location ?? 0}
          onChange={(event) => set("extra_location", Math.max(0, Math.min(50, Number(event.target.value) || 0)))}
          aria-label={t("names.extra_location")}
          className="control w-20 px-2 py-1.5 text-center"
        />
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
