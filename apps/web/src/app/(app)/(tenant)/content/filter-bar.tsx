"use client";

import { Calendar, Check, ChevronDown, GitCompareArrows, RotateCcw, SlidersHorizontal, X } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useId, useRef, useState, useTransition } from "react";

import { useDismiss } from "@/components/use-dismiss";

import { NetworkIcon } from "./network-icon";
import type { Range } from "./filters";

const RANGES: Range[] = ["7", "30", "90", "month", "last_month", "custom"];

type Labels = {
  bar: string;
  networks: string;
  allNetworks: string;
  selectAll: string;
  period: string;
  compare: string;
  compareShort: string;
  from: string;
  to: string;
  reset: string;
  filtersButton: string;
  remove: string;
  ranges: Record<Range, string>;
};

type View = { chosen: string[]; range: Range; from: string; to: string; compare: boolean };

/** A popover under its button; closes on outside click and Escape. */
function Popover({ label, icon, summary, children, width = "w-64" }: { label: string; icon: React.ReactNode; summary: string; children: React.ReactNode; width?: string }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, root, button);
  return (
    <div ref={root} className="relative">
      <button
        ref={button}
        type="button"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`${label}: ${summary}`}
        onClick={() => setOpen((value) => !value)}
        className="control flex items-center gap-2 px-3 py-2 text-sm font-medium"
      >
        {icon}
        <span>{summary}</span>
        <ChevronDown aria-hidden="true" className="size-4 text-muted" />
      </button>
      <div id={panelId} role="group" aria-label={label} data-open={open} className={`popover absolute start-0 top-full z-30 mt-2 flex max-w-[calc(100vw-2rem)] origin-top flex-col gap-1 p-2 ${width}`}>
        {children}
      </div>
    </div>
  );
}

export function FilterBar({
  networks,
  chosen,
  range,
  from,
  to,
  compare,
  sort,
  labels,
}: {
  networks: { value: string; label: string }[];
  chosen: string[];
  range: Range;
  from: string;
  to: string;
  compare: boolean;
  sort: string;
  labels: Labels;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [pending, startTransition] = useTransition();
  const [sheet, setSheet] = useState(false);

  const apply = (next: Partial<View>) => {
    const view: View = { chosen, range, from, to, compare, ...next };
    const params = new URLSearchParams();
    for (const network of view.chosen) params.append("network", network);
    params.set("range", view.range);
    if (view.range === "custom") {
      params.set("from", view.from);
      params.set("to", view.to);
    }
    if (view.compare) params.set("compare", "1");
    params.set("sort", sort);
    startTransition(() => router.replace(`${pathname}?${params.toString()}`, { scroll: false }));
  };

  const toggleNetwork = (value: string) => {
    const base = chosen.length === 0 ? networks.map((n) => n.value) : chosen;
    const next = base.includes(value) ? base.filter((n) => n !== value) : [...base, value];
    // Every network picked is the same view as none picked: keep the address short.
    apply({ chosen: next.length === networks.length ? [] : next });
  };

  const active = chosen.length > 0 ? networks.filter((n) => chosen.includes(n.value)) : [];
  const networkSummary = chosen.length === 0 || chosen.length === networks.length ? labels.allNetworks : chosen.length === 1 ? (active[0]?.label ?? "") : `${chosen.length} / ${networks.length}`;
  const dirty = chosen.length > 0 || range !== "30" || compare;
  const count = (chosen.length > 0 ? 1 : 0) + (range !== "30" ? 1 : 0) + (compare ? 1 : 0);

  const optionClass = "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-normal transition-colors hover:bg-foreground/5 has-[:focus-visible]:bg-foreground/5";
  const box = "grid size-4 shrink-0 place-items-center rounded border border-border text-transparent peer-checked:border-primary peer-checked:bg-primary peer-checked:text-on-primary";
  const dot = "grid size-4 shrink-0 place-items-center rounded-full border border-border peer-checked:border-[5px] peer-checked:border-primary";

  return (
    <section aria-label={labels.bar} aria-busy={pending} className="card sticky top-2 z-20 flex flex-col gap-3 p-3 print:hidden">
      <button type="button" aria-expanded={sheet} onClick={() => setSheet((value) => !value)} className="btn-secondary flex items-center justify-center gap-2 px-4 py-2 sm:hidden">
        <SlidersHorizontal aria-hidden="true" className="size-4" />
        {labels.filtersButton}
        {count > 0 && <span className="rounded-full bg-primary px-2 text-xs font-bold text-on-primary">{count}</span>}
      </button>
      <div className={`${sheet ? "flex" : "hidden"} flex-col gap-3 sm:flex`}>
        <div className="flex flex-wrap items-center gap-2">
          <Popover label={labels.networks} summary={networkSummary} icon={<span aria-hidden="true" className="size-2 rounded-full bg-primary" />} width="w-72">
            <div className="px-2 pb-1">
              <button type="button" onClick={() => apply({ chosen: [] })} className="btn-link text-xs font-semibold text-primary-ink hover:underline">
                {labels.selectAll}
              </button>
            </div>
            {networks.map(({ value, label }) => (
              <label key={value} className={optionClass}>
                <input type="checkbox" checked={chosen.length === 0 || chosen.includes(value)} onChange={() => toggleNetwork(value)} className="peer sr-only" />
                <span aria-hidden="true" className={box}>
                  <Check className="size-3" />
                </span>
                <NetworkIcon network={value} size="sm" />
                {label}
              </label>
            ))}
          </Popover>

          <Popover label={labels.period} summary={labels.ranges[range]} icon={<Calendar aria-hidden="true" className="size-4 text-muted" />} width="w-72">
            {RANGES.map((value) => (
              <label key={value} className={optionClass}>
                <input type="radio" name="range" checked={range === value} onChange={() => apply({ range: value, from, to })} className="peer sr-only" />
                <span aria-hidden="true" className={dot} />
                {labels.ranges[value]}
              </label>
            ))}
            {range === "custom" && (
              <div className="mt-1 grid grid-cols-2 gap-2 border-t border-border px-1 pt-2">
                <label className="flex flex-col gap-1 text-xs font-medium">
                  {labels.from}
                  <input type="date" value={from} max={to} onChange={(e) => e.target.value && apply({ from: e.target.value })} className="control px-2 py-1.5 text-sm" />
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium">
                  {labels.to}
                  <input type="date" value={to} min={from} onChange={(e) => e.target.value && apply({ to: e.target.value })} className="control px-2 py-1.5 text-sm" />
                </label>
              </div>
            )}
          </Popover>

          <button
            type="button"
            role="switch"
            aria-checked={compare}
            aria-label={labels.compare}
            onClick={() => apply({ compare: !compare })}
            className={`btn-plain flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium ring-1 transition-colors ${compare ? "bg-primary/10 text-primary-ink ring-primary" : "bg-surface ring-border hover:bg-foreground/5"}`}
          >
            <GitCompareArrows aria-hidden="true" className="size-4" />
            {labels.compareShort}
          </button>

          {dirty && (
            <button type="button" onClick={() => apply({ chosen: [], range: "30", compare: false })} className="btn-plain ms-auto flex items-center gap-1.5 rounded-lg px-2 py-2 text-sm font-medium text-muted hover:text-foreground">
              <RotateCcw aria-hidden="true" className="size-4" />
              {labels.reset}
            </button>
          )}
        </div>

        {active.length > 0 && (
          <ul className="flex flex-wrap items-center gap-2">
            {active.map(({ value, label }) => (
              <li key={value}>
                <button
                  type="button"
                  aria-label={`${labels.remove}: ${label}`}
                  onClick={() => toggleNetwork(value)}
                  className="btn-plain flex items-center gap-2 rounded-full bg-surface py-1 ps-1.5 pe-2.5 text-sm font-medium ring-1 ring-border transition-colors hover:bg-foreground/5"
                >
                  <NetworkIcon network={value} size="sm" />
                  {label}
                  <X aria-hidden="true" className="size-3.5 text-muted" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
