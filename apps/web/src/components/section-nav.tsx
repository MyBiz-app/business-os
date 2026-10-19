"use client";

import Link from "next/link";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { scrollToSection } from "@/lib/scroll-to-section";

import { useScrollSpy } from "./use-scroll-spy";

/** A section of the page (`id`) or, with `href`, a page of its own that opens as a normal link. */
export type SectionNavItem = { id: string; label: ReactNode; icon?: ReactNode; href?: string; group?: ReactNode; current?: boolean };

/**
 * The inner menu of a long page. A click scrolls smoothly to that section (opening it if it is
 * folded, and landing it fully below the sticky header) and keeps the address `#id` in step without a jump; while the page scrolls the section
 * being read is marked. Wide screens: a sticky column. Narrow screens: a bar of buttons that sticks
 * under the app header and keeps the marked one in view, with touch-sized targets.
 */
export function SectionNav({ items, label }: { items: SectionNavItem[]; label: string }) {
  const sections = items.filter((item) => !item.href).map((item) => item.id);
  const spied = useScrollSpy(sections);
  // A click marks its section at once; the scroll spy takes over when the scroll has settled.
  const [clicked, setClicked] = useState<string | null>(null);
  const bar = useRef<HTMLUListElement>(null);
  const active = clicked ?? spied ?? sections[0] ?? null;

  // The clicked item stays marked until the person scrolls on their own; then the scroll spy takes over.
  useEffect(() => {
    if (clicked === null) return;
    const release = () => setClicked(null);
    const types = ["wheel", "touchmove", "keydown"];
    for (const type of types) window.addEventListener(type, release, { passive: true });
    return () => {
      for (const type of types) window.removeEventListener(type, release);
    };
  }, [clicked]);

  // On the narrow bar, bring the marked button into view without moving the page.
  useEffect(() => {
    const list = bar.current;
    const current = list?.querySelector<HTMLElement>("[data-current]");
    if (!list || !current || list.scrollWidth <= list.clientWidth) return;
    list.scrollTo({ left: current.offsetLeft - (list.clientWidth - current.offsetWidth) / 2, behavior: "smooth" });
  }, [active]);

  function go(event: React.MouseEvent<HTMLAnchorElement>, id: string) {
    event.preventDefault();
    setClicked(id);
    try {
      window.history.replaceState(null, "", `#${id}`);
    } catch {
      // Not critical: the page still scrolls.
    }
    scrollToSection(id);
  }

  return (
    <nav
      aria-label={label}
      className="section-nav sticky top-14 z-20 -mx-[var(--swipe-gutter,1rem)] border-b border-border bg-background/95 px-[var(--swipe-gutter,1rem)] backdrop-blur print:hidden md:top-16 lg:top-24 lg:mx-0 lg:border-0 lg:bg-transparent lg:px-0 lg:backdrop-blur-none"
    >
      <ul ref={bar} className="flex gap-1 overflow-x-auto py-2 [scrollbar-width:none] lg:flex-col lg:overflow-visible lg:py-0">
        {items.map((item, index) => {
          const isCurrent = item.href ? !!item.current : item.id === active;
          const heading = item.group && item.group !== items[index - 1]?.group ? item.group : null;
          const classes = `flex min-h-11 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl px-3.5 py-2 text-sm transition-colors lg:min-h-10 lg:w-full lg:whitespace-normal ${
            isCurrent ? "bg-primary/10 font-semibold text-foreground" : "text-foreground hover:bg-foreground/5"
          }`;
          return (
            <li key={item.id} data-current={isCurrent || undefined} className="lg:w-full">
              {heading && <p className="mb-1 mt-4 hidden px-3 text-xs font-semibold uppercase tracking-wide text-muted lg:block">{heading}</p>}
              {item.href ? (
                <Link href={item.href} aria-current={isCurrent ? "page" : undefined} className={classes}>
                  {item.icon}
                  <span>{item.label}</span>
                </Link>
              ) : (
                <a href={`#${item.id}`} onClick={(event) => go(event, item.id)} aria-current={isCurrent ? "location" : undefined} className={classes}>
                  {item.icon}
                  <span>{item.label}</span>
                </a>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
