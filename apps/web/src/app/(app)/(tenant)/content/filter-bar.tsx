"use client";

import { Calendar, Check, ChevronDown, GitCompareArrows, RotateCcw, SlidersHorizontal, X } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Popover } from "@/components/ui/popover";

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
function FilterPopover({ label, icon, summary, children, width = "w-64" }: { label: string; icon: React.ReactNode; summary: string; children: React.ReactNode; width?: string }) {
  return (
    <Popover
      label={label}
      className={`flex flex-col gap-1 p-2 ${width}`}
      trigger={(props) => (
        <Button {...props} variant="plain" aria-label={`${label}: ${summary}`} className="control flex items-center gap-2 px-3 py-2 text-sm font-medium">
          {icon}
          <span>{summary}</span>
          <ChevronDown aria-hidden="true" className="size-4 text-muted" />
        </Button>
      )}
    >
      {children}
    </Popover>
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

  const optionClass = "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-normal transition-colors hover:bg-subtle has-[:focus-visible]:bg-subtle";
  const box = "grid size-4 shrink-0 place-items-center rounded border border-border text-transparent peer-checked:border-primary peer-checked:bg-primary peer-checked:text-on-primary";
  const dot = "grid size-4 shrink-0 place-items-center rounded-full border border-border peer-checked:border-[5px] peer-checked:border-primary";

  return (
    <section aria-label={labels.bar} aria-busy={pending} className="card sticky-below-header z-20 flex flex-col gap-3 p-3 print:hidden">
      <Button variant="secondary" aria-expanded={sheet} onClick={() => setSheet((value) => !value)} className="justify-center sm:hidden">
        <SlidersHorizontal aria-hidden="true" className="size-4" />
        {labels.filtersButton}
        {count > 0 && <span className="rounded-full bg-primary px-2 text-xs font-semibold text-on-primary">{count}</span>}
      </Button>
      <div className={`${sheet ? "flex" : "hidden"} flex-col gap-3 sm:flex`}>
        <div className="flex flex-wrap items-center gap-2">
          <FilterPopover label={labels.networks} summary={networkSummary} icon={<span aria-hidden="true" className="size-2 rounded-full bg-primary" />} width="w-72">
            <div className="px-2 pb-1">
              <Button variant="quiet" onClick={() => apply({ chosen: [] })} className="text-xs text-primary-ink">
                {labels.selectAll}
              </Button>
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
          </FilterPopover>

          <FilterPopover label={labels.period} summary={labels.ranges[range]} icon={<Calendar aria-hidden="true" className="size-4 text-muted" />} width="w-72">
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
          </FilterPopover>

          <Button
            variant="plain"
            role="switch"
            aria-checked={compare}
            aria-label={labels.compare}
            onClick={() => apply({ compare: !compare })}
            className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium ring-1 transition-colors ${compare ? "bg-primary-subtle text-primary-ink ring-primary" : "bg-surface ring-border hover:bg-subtle"}`}
          >
            <GitCompareArrows aria-hidden="true" className="size-4" />
            {labels.compareShort}
          </Button>

          {dirty && (
            <Button variant="quiet" onClick={() => apply({ chosen: [], range: "30", compare: false })} className="ms-auto">
              <RotateCcw aria-hidden="true" className="size-4" />
              {labels.reset}
            </Button>
          )}
        </div>

        {active.length > 0 && (
          <ul className="flex flex-wrap items-center gap-2">
            {active.map(({ value, label }) => (
              <li key={value}>
                <Button
                  variant="plain"
                  aria-label={`${labels.remove}: ${label}`}
                  onClick={() => toggleNetwork(value)}
                  className="flex items-center gap-2 rounded-full bg-surface py-1 ps-1.5 pe-2.5 text-sm font-medium ring-1 ring-border transition-colors hover:bg-subtle"
                >
                  <NetworkIcon network={value} size="sm" />
                  {label}
                  <X aria-hidden="true" className="size-3.5 text-muted" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
