"use client";

import { useLayoutEffect, useRef, useState } from "react";

/** A row of buttons where one is active (text size, contrast, motion, tabs, periods). The active
 * pill slides to the chosen option instead of jumping; pair it with `ContentSwap` to fade the
 * content below. Changes a setting in place; the linked `Segmented` on the shift board is the
 * navigating twin. */
export function SegmentedControl<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  const group = useRef<HTMLDivElement>(null);
  const [pill, setPill] = useState<{ x: number; width: number } | null>(null);

  useLayoutEffect(() => {
    const element = group.current;
    if (!element) return;
    function measure() {
      const active = element?.querySelector<HTMLElement>('[aria-pressed="true"]');
      // offsetLeft is measured from the physical left edge, so it is right in RTL as well.
      setPill(active ? { x: active.offsetLeft, width: active.offsetWidth } : null);
    }
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [value, options]);

  return (
    <div
      ref={group}
      role="group"
      aria-label={label}
      className="relative flex max-w-full overflow-x-auto rounded-xl bg-surface-2 p-0.5 ring-1 ring-border"
    >
      {pill ? (
        <span
          aria-hidden="true"
          className="segmented-pill"
          style={{ left: 0, width: pill.width, transform: `translateX(${pill.x}px)` }}
        />
      ) : null}
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={`btn-plain relative shrink-0 whitespace-nowrap rounded-[0.6rem] px-3 py-2 text-sm md:py-1.5 transition-colors ${
            value === option.value ? "font-semibold text-foreground" : "text-muted hover:text-foreground"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
