"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import type { Catalog } from "@/lib/pricing";
import { formatMoney } from "@/lib/money";
import { type ModuleKey, type PriceLine } from "@/lib/signup-plan";

/** A number that rolls to its new value (instantly with reduced motion). */
export function useRolling(target: number): number {
  const [value, setValue] = useState(target);
  const from = useRef(target);
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const start = from.current;
    if (reduced || start === target) {
      from.current = target;
      setValue(target);
      return;
    }
    const begin = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - begin) / 350);
      const current = Math.round(start + (target - start) * (1 - (1 - progress) ** 3));
      from.current = current;
      setValue(current);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target]);
  return value;
}

type Props = {
  catalog: Catalog;
  locale: string;
  lines: PriceLine[];
  once: PriceLine[];
  total: number;
  onceTotal: number;
  /** The active-client count, for the "per client" figure (0: not shown). */
  clients: number;
  tierName: string;
};

/** The live receipt: one line per charge, the monthly total, the price per day and per client,
 * and the one-time charges (setup) apart. */
export function CalcReceipt({ catalog, locale, lines, once, total, onceTotal, clients, tierName }: Props) {
  const t = useTranslations("marketing.pricing.calc");
  const tp = useTranslations("marketing.pricing");
  const tModules = useTranslations("modules");
  const money = (amount: number) => formatMoney(amount, catalog.currency, locale);
  const rolling = useRolling(total);
  const label = (line: PriceLine) =>
    line.key === "core" ? t("coreLine", { tier: tierName }) : `${tModules(`names.${line.key as ModuleKey}` as "names.client_app")}${line.quantity > 1 ? ` ×${line.quantity}` : ""}`;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm font-semibold text-primary-ink">{t("receiptTitle")}</p>
      <ul className="flex flex-col gap-1.5 border-y border-dashed border-border py-3 text-sm tabular-nums">
        {lines.map((line) => (
          <li key={line.key} className="flex justify-between gap-3">
            <span>{label(line)}</span>
            <bdi>{money(line.amount)}</bdi>
          </li>
        ))}
      </ul>
      <div>
        <p className="text-sm text-muted">{t("total")}</p>
        <p className="flex items-baseline gap-1">
          <span aria-hidden="true" className="text-5xl font-extrabold tracking-tight tabular-nums">
            <bdi>{money(rolling)}</bdi>
          </span>
          <span className="sr-only">{money(total)}</span>
          <span className="text-muted">{tp("perMonth")}</span>
        </p>
      </div>
      <p className="text-sm text-muted">
        {t("daily", { price: money(Math.ceil(total / 30)) })}
        {clients > 0 && <> · {t("perClient", { price: money(Math.ceil(total / clients)) })}</>}
      </p>
      {once.length > 0 && (
        <div className="rounded-xl bg-foreground/5 p-3 text-sm">
          <p className="font-semibold">{t("onceTitle")}</p>
          <ul className="mt-1 flex flex-col gap-1 tabular-nums">
            {once.map((line) => (
              <li key={line.key} className="flex justify-between gap-3">
                <span>{label(line)}</span>
                <bdi>{money(line.amount)}</bdi>
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-muted">{t("onceNote", { price: money(onceTotal) })}</p>
        </div>
      )}
      <p className="text-sm font-medium">{tp("trialNote")}</p>
    </div>
  );
}
