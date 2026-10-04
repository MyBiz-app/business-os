"use client";

import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import { formatMoney } from "@/lib/money";

type Props = {
  value: number;
  /** money: minor units; percent: 0–100. */
  kind: "money" | "percent" | "count";
  currency?: string;
  durationMs?: number;
};

/** A number that counts up from zero when it first appears. Screen readers get the final
 * value only; the animation is skipped when the user prefers reduced motion. */
export function CountUp({ value, kind, currency = "ILS", durationMs = 900 }: Props) {
  const locale = useLocale();
  const [shown, setShown] = useState(0);

  useEffect(() => {
    const instant = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = instant ? 1 : Math.min((now - start) / durationMs, 1);
      const eased = 1 - (1 - progress) ** 3;
      setShown(progress === 1 ? value : value * eased);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, durationMs]);

  // While counting, money shows whole units only; the final value is exact.
  const format = (n: number) =>
    kind === "money"
      ? formatMoney(n === value ? n : Math.round(n / 100) * 100, currency, locale)
      : kind === "percent"
        ? `${new Intl.NumberFormat(locale).format(Math.round(n))}%`
        : new Intl.NumberFormat(locale).format(Math.round(n));

  return (
    <>
      <span aria-hidden="true" className="tabular-nums">
        {format(shown)}
      </span>
      <span className="sr-only">{format(value)}</span>
    </>
  );
}
