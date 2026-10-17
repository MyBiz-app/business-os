"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { createContext, type ReactNode, useContext, useId, useState, useTransition } from "react";

import { PendingContent } from "@/components/ui/loading";
import { formatDay } from "@/lib/dates";
import { rangeShortcuts } from "@/lib/range";

import { SegmentedControl } from "./segmented-control";

const Pending = createContext(false);
const Navigate = createContext<(query: URLSearchParams) => void>(() => {});

/** Holds the "numbers are loading" state for a page whose period can change. The picker inside
 * it changes the link without leaving the spot the person is at; `PendingArea` dims the old
 * numbers and shows dots until the new ones arrive. */
export function PeriodProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [pending, start] = useTransition();
  const go = (query: URLSearchParams) => {
    const text = query.toString();
    start(() => router.replace(text ? `${pathname}?${text}` : pathname, { scroll: false }));
  };
  return (
    <Navigate value={go}>
      <Pending value={pending}>{children}</Pending>
    </Navigate>
  );
}

/** The part of the page that shows the numbers of the chosen period. */
export function PendingArea({ children, className }: { children: ReactNode; className?: string }) {
  const t = useTranslations("period");
  const pending = useContext(Pending);
  return (
    <div className={className}>
      <PendingContent pending={pending} label={t("loading")}>
        {children}
      </PendingContent>
    </div>
  );
}

const short = { day: "numeric", month: "numeric" } as const;

type Props = {
  /** The preset lengths in days, e.g. [7, 30, 90]. */
  presets: readonly number[];
  /** The chosen preset ("30"), "custom", or another key from `extra` (e.g. "month"). */
  value: string;
  /** The free range in the link, when `value` is "custom". */
  from?: string;
  to?: string;
  /** Today in the business's time zone: the latest day a free range may end. */
  today: string;
  /** Extra choices before the presets: they only drop the period from the link. */
  extra?: { value: string; label: string }[];
  /** Link parameters that belong to other choices (kept out when the period changes). */
  reset?: string[];
};

/** 7 / 30 / 90 days and "Range...": a sliding pill that changes the page's period in place. */
export function PeriodPicker({ presets, value, from, to, today, extra = [], reset = [] }: Props) {
  const t = useTranslations("period");
  const locale = useLocale();
  const go = useContext(Navigate);
  const params = useSearchParams();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({ from: from ?? "", to: to ?? "" });
  const panel = useId();

  const base = () => {
    const query = new URLSearchParams(params.toString());
    for (const key of ["period", "from", "to", "page", ...reset]) query.delete(key);
    return query;
  };
  const apply = (range: { from: string; to: string }) => {
    const query = base();
    query.set("from", range.from);
    query.set("to", range.to);
    setOpen(false);
    go(query);
  };
  const choose = (next: string) => {
    if (next === "custom") {
      setDraft({ from: from ?? "", to: to ?? "" });
      setOpen((was) => !was);
      return;
    }
    setOpen(false);
    const query = base();
    if (/^\d+$/.test(next)) query.set("period", next);
    else query.set(next, "");
    go(query);
  };
  const valid = draft.from !== "" && draft.to !== "" && draft.from <= draft.to && draft.to <= today;
  const customLabel =
    value === "custom" && from && to ? t("customLabel", { from: formatDay(from, locale, short), to: formatDay(to, locale, short) }) : t("custom");

  return (
    <div className="relative flex w-full sm:w-auto">
      <SegmentedControl
        label={t("label")}
        value={value}
        options={[
          ...extra,
          ...presets.map((days) => ({ value: String(days), label: t("lastDays", { count: days }) })),
          { value: "custom", label: customLabel },
        ]}
        onChange={choose}
      />
      {open && (
        <div
          id={panel}
          role="group"
          aria-label={t("custom")}
          className="card absolute end-0 top-full z-30 mt-2 flex w-72 flex-col gap-3 p-4 shadow-lg"
        >
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-sm font-medium">
              {t("from")}
              <input
                type="date"
                value={draft.from}
                max={today}
                onChange={(event) => setDraft((d) => ({ ...d, from: event.target.value }))}
                className="control px-2 py-1.5 font-normal"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium">
              {t("to")}
              <input
                type="date"
                value={draft.to}
                max={today}
                onChange={(event) => setDraft((d) => ({ ...d, to: event.target.value }))}
                className="control px-2 py-1.5 font-normal"
              />
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            {rangeShortcuts(today).map((shortcut) => (
              <button
                key={shortcut.key}
                type="button"
                onClick={() => apply(shortcut)}
                className="btn-secondary px-3 py-1 text-xs"
              >
                {t(shortcut.key)}
              </button>
            ))}
          </div>
          {draft.from !== "" && draft.to !== "" && !valid && (
            <p role="alert" className="text-xs text-danger">
              {t("invalid")}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setOpen(false)} className="btn-secondary px-3 py-1.5 text-sm">
              {t("cancel")}
            </button>
            <button type="button" disabled={!valid} onClick={() => apply(draft)} className="btn-primary px-3 py-1.5 text-sm">
              {t("apply")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
