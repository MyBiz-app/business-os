"use client";

import { useLocale } from "next-intl";
import { useId, useState } from "react";

export type Column = { key: string; label: string; value: number; display: string };

type Props = {
  title: string;
  columns: Column[];
  /** How axis ticks are formatted (compact). Money values are in minor units. */
  unit: { kind: "count" } | { kind: "money"; currency: string };
  tableLabel: string;
  headers: [string, string];
};

const HEIGHT = 180;
const AXIS = 60; // room for y-axis tick labels
const MAX_BAR = 24;

/** Rounds up to a clean axis maximum (1, 2, 2.5, 5 × 10^n). */
function niceMax(value: number): number {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((s) => s * power >= value) ?? 10;
  return step * power;
}

/** A single-series column chart: thin columns from one baseline, hover/focus tooltip and a
 * table view. One series, so the title names it and there is no legend. */
export function ColumnChart({ title, columns, unit, tableLabel, headers }: Props) {
  const id = useId();
  const locale = useLocale();
  const compact = new Intl.NumberFormat(locale, {
    notation: "compact",
    maximumFractionDigits: 1,
    ...(unit.kind === "money" ? { style: "currency", currency: unit.currency } : {}),
  });
  const formatTick = (value: number) => compact.format(unit.kind === "money" ? value / 100 : value);
  const [active, setActive] = useState<number | null>(null);
  const max = niceMax(Math.max(...columns.map((c) => c.value), 0));
  const ticks = [0, max / 2, max];
  const width = 640;
  const slot = (width - AXIS) / Math.max(columns.length, 1);
  const bar = Math.min(MAX_BAR, slot * 0.6);
  const y = (value: number) => HEIGHT - (value / max) * HEIGHT;
  const current = active === null ? null : columns[active];

  return (
    <figure className="flex flex-col gap-3" aria-labelledby={`${id}-title`}>
      <figcaption id={`${id}-title`} className="font-semibold">
        {title}
      </figcaption>
      <div className="relative" dir="ltr">
        <svg viewBox={`0 0 ${width} ${HEIGHT + 28}`} className="h-auto w-full overflow-visible" role="img" aria-label={title}>
          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={AXIS} x2={width} y1={y(tick)} y2={y(tick)} className="stroke-border" strokeWidth={1} />
              <text x={AXIS - 8} y={y(tick)} textAnchor="end" dominantBaseline="middle" className="fill-muted text-[15px]">
                {formatTick(tick)}
              </text>
            </g>
          ))}
          {columns.map((column, index) => {
            const x = AXIS + slot * index + (slot - bar) / 2;
            const top = y(column.value);
            const h = HEIGHT - top;
            const r = Math.min(4, h, bar / 2);
            return (
              <g
                key={column.key}
                tabIndex={0}
                role="graphics-symbol"
                aria-label={`${column.label}: ${column.display}`}
                onMouseEnter={() => setActive(index)}
                onMouseLeave={() => setActive(null)}
                onFocus={() => setActive(index)}
                onBlur={() => setActive(null)}
                className="outline-none"
              >
                {/* Hit target: the whole slot, taller than the mark. */}
                <rect x={AXIS + slot * index} y={0} width={slot} height={HEIGHT} fill="transparent" />
                {h > 0 && (
                  <path
                    d={`M${x},${HEIGHT} V${top + r} Q${x},${top} ${x + r},${top} H${x + bar - r} Q${x + bar},${top} ${x + bar},${top + r} V${HEIGHT} Z`}
                    className={active === index ? "fill-primary" : "fill-primary/80"}
                  />
                )}
                {(index % Math.ceil(columns.length / 8) === 0 || index === columns.length - 1) && (
                  <text x={x + bar / 2} y={HEIGHT + 20} textAnchor="middle" className="fill-muted text-[15px]">
                    {column.label}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
        {current && active !== null && (
          <div
            role="status"
            className="pointer-events-none absolute -top-2 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs shadow-sm"
            style={{ left: `${((AXIS + slot * active + slot / 2) / width) * 100}%`, transform: "translate(-50%, -100%)" }}
          >
            <span className="text-muted">{current.label}</span> · <span className="font-semibold">{current.display}</span>
          </div>
        )}
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer text-muted">{tableLabel}</summary>
        <table className="mt-2 w-full text-start">
          <thead>
            <tr className="text-muted">
              <th className="py-1 text-start font-medium">{headers[0]}</th>
              <th className="py-1 text-end font-medium">{headers[1]}</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((column) => (
              <tr key={column.key} className="border-t border-border">
                <td className="py-1">{column.label}</td>
                <td className="py-1 text-end tabular-nums">{column.display}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
