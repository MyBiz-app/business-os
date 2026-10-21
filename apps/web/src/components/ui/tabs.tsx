"use client";

import Link from "next/link";
import { type KeyboardEvent, type ReactNode, useLayoutEffect, useRef, useState } from "react";

import { cx } from "./cx";

export type TabItem<T extends string = string> = {
  value: T;
  label: ReactNode;
  /** A count or a short status after the label. */
  badge?: ReactNode;
  /** Makes the tab a link to another address (a page per tab). Without it the tab is a button. */
  href?: string;
};

const TAB = "btn-plain relative inline-flex shrink-0 items-center gap-2 whitespace-nowrap px-3 py-2.5 text-sm font-medium transition-colors min-h-10";

/** Underline tabs. With `onChange` they switch content on the same page (a tab list with a
 * `TabPanel` each: the arrow keys, Home and End move between them). With `href` on the items they
 * are links, one address per tab, and the open one is `aria-current`; the page never jumps. The
 * underline glides to the chosen tab (instantly under "reduce motion"). */
export function Tabs<T extends string>({
  label,
  items,
  value,
  onChange,
  idPrefix,
  className,
}: {
  /** The tab list's name for screen readers. */
  label: string;
  items: TabItem<T>[];
  value: T;
  onChange?: (value: T) => void;
  /** Ties each tab to its `TabPanel` (same prefix). Needed for button tabs. */
  idPrefix?: string;
  className?: string;
}) {
  const list = useRef<HTMLDivElement>(null);
  const [bar, setBar] = useState<{ x: number; width: number } | null>(null);
  const [glide, setGlide] = useState(false);
  const linked = items.some((item) => item.href);

  useLayoutEffect(() => {
    const element = list.current;
    if (!element) return;
    function measure() {
      const active = element?.querySelector<HTMLElement>('[data-active="true"]');
      // offsetLeft is measured from the physical left edge, so it is right in RTL as well.
      setBar(active ? { x: active.offsetLeft, width: active.offsetWidth } : null);
    }
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    const frame = requestAnimationFrame(() => setGlide(true));
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [value, items]);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (linked) return;
    const keys = ["ArrowRight", "ArrowLeft", "Home", "End"];
    if (!keys.includes(event.key)) return;
    event.preventDefault();
    const index = items.findIndex((item) => item.value === value);
    // In a right-to-left page the arrows point the other way.
    const step = (event.key === "ArrowRight" ? 1 : -1) * (getComputedStyle(event.currentTarget).direction === "rtl" ? -1 : 1);
    const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : (index + step + items.length) % items.length;
    onChange?.(items[next].value);
    requestAnimationFrame(() => list.current?.querySelector<HTMLElement>('[data-active="true"]')?.focus());
  }

  const children = items.map((item) => {
    const active = item.value === value;
    const className = cx(TAB, active ? "text-foreground" : "text-muted hover:text-foreground");
    const content = (
      <>
        {item.label}
        {item.badge !== undefined && <span className="rounded-full bg-subtle px-1.5 text-xs tabular-nums text-muted">{item.badge}</span>}
      </>
    );
    if (item.href) {
      return (
        <Link key={item.value} href={item.href} scroll={false} data-active={active} aria-current={active ? "page" : undefined} className={className}>
          {content}
        </Link>
      );
    }
    return (
      <button
        key={item.value}
        type="button"
        role="tab"
        id={idPrefix ? `${idPrefix}-tab-${item.value}` : undefined}
        aria-selected={active}
        aria-controls={idPrefix ? `${idPrefix}-panel-${item.value}` : undefined}
        tabIndex={active ? 0 : -1}
        data-active={active}
        onClick={() => onChange?.(item.value)}
        className={className}
      >
        {content}
      </button>
    );
  });

  const track = (
    <div
      ref={list}
      role={linked ? undefined : "tablist"}
      aria-label={linked ? undefined : label}
      onKeyDown={onKeyDown}
      className={cx("relative isolate flex max-w-full overflow-x-auto border-b border-border", className)}
    >
      {children}
      {bar && (
        <span
          aria-hidden="true"
          className={cx("pointer-events-none absolute bottom-0 h-0.5 rounded-full bg-primary motion-reduce:transition-none", glide && "transition-[transform,width] duration-200 ease-out")}
          style={{ left: 0, width: bar.width, transform: `translateX(${bar.x}px)` }}
        />
      )}
    </div>
  );
  return linked ? <nav aria-label={label}>{track}</nav> : track;
}

/** The content of one tab. Render it for every tab and pass `active`; the others stay hidden. */
export function TabPanel({ idPrefix, value, active, children, className }: { idPrefix: string; value: string; active: boolean; children: ReactNode; className?: string }) {
  return (
    <div role="tabpanel" id={`${idPrefix}-panel-${value}`} aria-labelledby={`${idPrefix}-tab-${value}`} hidden={!active} tabIndex={0} className={className}>
      {active ? children : null}
    </div>
  );
}
