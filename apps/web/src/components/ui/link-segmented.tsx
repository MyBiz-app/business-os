"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLayoutEffect, useRef, useState, useTransition } from "react";

import { LoadingDots } from "@/components/ui/loading";

export type LinkSegmentedOption = { key: string; label: string; href: string };

/** The navigating twin of `SegmentedControl`: each option is a link (so the choice lives in the
 * URL and can be shared), but the pill slides at once to the option you picked, the page stays
 * where it is (no jump to the top) and dots show while the new data loads. Use it for periods,
 * filters, views and any other pair or row of choices that changes what a page shows. */
export function LinkSegmented({
  label,
  loadingLabel,
  options,
  active,
  variant = "pill",
}: {
  label: string;
  loadingLabel: string;
  options: LinkSegmentedOption[];
  active: string;
  /** "pill": a sliding pill in a track (default). "chips": separate rounded chips, no track. */
  variant?: "pill" | "chips";
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [chosen, setChosen] = useState<string | null>(null);
  const selected = pending && chosen ? chosen : active;
  const group = useRef<HTMLElement>(null);
  const [pill, setPill] = useState<{ x: number; width: number } | null>(null);

  useLayoutEffect(() => {
    const element = group.current;
    if (!element || variant !== "pill") return;
    function measure() {
      const current = element?.querySelector<HTMLElement>('[aria-current="true"]');
      // offsetLeft is measured from the physical left edge, so it is right in RTL as well.
      setPill(current ? { x: current.offsetLeft, width: current.offsetWidth } : null);
    }
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [selected, options, variant]);

  function choose(event: React.MouseEvent<HTMLAnchorElement>, option: LinkSegmentedOption) {
    // Let the browser handle new-tab clicks; everything else is a soft in-place change.
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault();
    if (option.key === selected) return;
    setChosen(option.key);
    startTransition(() => router.push(option.href, { scroll: false }));
  }

  return (
    <nav
      ref={group}
      aria-label={label}
      aria-busy={pending}
      className={variant === "pill" ? "relative flex items-center rounded-xl bg-surface-2 p-0.5 ring-1 ring-border" : "flex flex-wrap items-center gap-2"}
    >
      {variant === "pill" && pill ? (
        <span aria-hidden="true" className="segmented-pill" style={{ left: 0, width: pill.width, transform: `translateX(${pill.x}px)` }} />
      ) : null}
      {options.map((option) => {
        const on = option.key === selected;
        return (
          <Link
            key={option.key}
            href={option.href}
            aria-current={on ? "true" : undefined}
            onClick={(event) => choose(event, option)}
            className={
              variant === "pill"
                ? `relative rounded-[0.6rem] px-3 py-1.5 text-sm transition-colors ${on ? "font-semibold text-foreground" : "text-muted hover:text-foreground"}`
                : `rounded-full border px-3 py-1 text-sm transition-colors ${on ? "border-primary bg-primary text-on-primary" : "border-border bg-surface"}`
            }
          >
            {option.label}
          </Link>
        );
      })}
      {pending ? <LoadingDots label={loadingLabel} className="ms-2 shrink-0" /> : null}
    </nav>
  );
}
