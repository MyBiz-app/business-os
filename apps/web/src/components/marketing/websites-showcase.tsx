"use client";

import { useEffect, useRef, useState } from "react";

export type ShowcaseSite = { key: string; label: string; name: string; line: string; button: string; items: string[]; tone: string };

/** The opening of /websites: a laptop frame whose sample site changes as the page scrolls (the
 * tall block pins the frame; scroll progress picks the site). The text of the active site is also
 * announced politely. Without JavaScript the first site stays; reduced motion drops the fade. */
export function WebsitesShowcase({ sites, heading, caption }: { sites: ShowcaseSite[]; heading: string; caption: string }) {
  const track = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const element = track.current;
    if (!element) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      const rect = element.getBoundingClientRect();
      const scrollable = rect.height - window.innerHeight;
      if (scrollable <= 0) return;
      const progress = Math.min(0.999, Math.max(0, -rect.top / scrollable));
      setIndex(Math.floor(progress * sites.length));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [sites.length]);

  const site = sites[index] ?? sites[0];
  if (!site) return null;

  return (
    <div ref={track} style={{ height: `${sites.length * 70 + 30}vh` }} className="relative">
      <div className="sticky top-16 flex h-[calc(100vh-4rem)] flex-col items-center justify-center gap-8 px-4 py-6">
        <p className="text-center text-sm font-semibold uppercase tracking-wide text-primary-ink">{heading}</p>
        <div className="w-full max-w-3xl" aria-hidden="true">
          <div className="rounded-t-2xl border border-border bg-navy p-2 shadow-2xl sm:p-3">
            <div key={site.key} className="mk-rise overflow-hidden rounded-lg bg-background">
              <div className="flex items-center gap-1.5 border-b border-border bg-surface px-3 py-2">
                <span className="size-2 rounded-full bg-danger" />
                <span className="size-2 rounded-full bg-warning" />
                <span className="size-2 rounded-full bg-success" />
                <span className="ms-3 truncate rounded-md bg-foreground/5 px-3 py-0.5 text-[11px] text-muted" dir="ltr">
                  {`${site.key}.example`}
                </span>
              </div>
              <div className={`flex flex-col gap-3 px-6 py-8 text-white sm:px-10 sm:py-12 ${site.tone}`}>
                <p className="text-xs font-semibold uppercase tracking-wide opacity-80">{site.name}</p>
                <p className="text-2xl font-extrabold leading-tight sm:text-4xl">{site.line}</p>
                <span className="mt-1 w-fit rounded-full bg-white px-5 py-2 text-xs font-bold text-navy sm:text-sm">{site.button}</span>
              </div>
              <div className="grid grid-cols-3 gap-3 p-4 sm:p-6">
                {site.items.map((item) => (
                  <div key={item} className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-3">
                    <span className={`h-10 rounded-lg opacity-80 sm:h-14 ${site.tone}`} />
                    <span className="truncate text-[11px] font-semibold sm:text-xs">{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="mx-auto h-3 rounded-b-2xl bg-foreground/15 sm:h-4" style={{ width: "108%", marginInlineStart: "-4%" }} />
        </div>
        <ol className="flex gap-2" aria-label={caption}>
          {sites.map((item, i) => (
            <li
              key={item.key}
              aria-current={i === index ? "step" : undefined}
              className={`rounded-full px-4 py-1.5 text-sm font-semibold transition-colors ${i === index ? "bg-primary text-on-primary" : "bg-foreground/5 text-muted"}`}
            >
              {item.label}
            </li>
          ))}
        </ol>
        <p className="sr-only" aria-live="polite">
          {site.label}: {site.line}
        </p>
      </div>
    </div>
  );
}
