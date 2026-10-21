import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { cx } from "./cx";

export type Trend = {
  direction: "up" | "down" | "flat";
  /** The change in words or numbers ("+12% vs last month"); the arrow only supports it. */
  label: string;
  /** Whether this change is good news (green), bad news (red) or neither. A fall in cancellations is good. */
  tone?: "good" | "bad" | "neutral";
};

const TREND_TONE = { good: "text-success-ink", bad: "text-danger", neutral: "text-muted" } as const;

function TrendLine({ trend }: { trend: Trend }) {
  const Icon = trend.direction === "up" ? ArrowUp : trend.direction === "down" ? ArrowDown : Minus;
  return (
    <span className={cx("inline-flex items-center gap-1 text-xs font-medium", TREND_TONE[trend.tone ?? "neutral"])}>
      <Icon aria-hidden="true" className="size-3.5" />
      <bdi>{trend.label}</bdi>
    </span>
  );
}

type StatTileProps = {
  label: string;
  value: ReactNode;
  /** A second line (a period, an amount). */
  hint?: ReactNode;
  trend?: Trend;
  /** Makes the whole tile a link to the list the number counts. */
  href?: string;
  /** The tile that matches the list shown now. */
  active?: boolean;
  className?: string;
};

/** One number with its label: 24px value, 13px label, an optional small trend. A tile with `href`
 * is a link to exactly what it counts, so the number and the list under it always agree. */
export function StatTile({ label, value, hint, trend, href, active = false, className }: StatTileProps) {
  const body = (
    <>
      <span className="text-sm text-muted">{label}</span>
      <span className="text-2xl font-semibold tabular-nums">{value}</span>
      {(hint || trend) && (
        <span className="flex flex-wrap items-center gap-x-2 text-xs text-muted">
          {trend && <TrendLine trend={trend} />}
          {hint}
        </span>
      )}
    </>
  );
  const base = cx("card flex h-full flex-col gap-1 p-4", active && "ring-2 ring-primary", className);
  if (!href) return <div className={base}>{body}</div>;
  return (
    <Link href={href} scroll={false} aria-current={active ? "true" : undefined} className={cx(base, "card-hover")}>
      {body}
    </Link>
  );
}
