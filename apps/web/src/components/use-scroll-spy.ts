"use client";

import { useEffect, useState } from "react";

import { stickyOffset } from "@/lib/scroll-to-section";

/** The id of the section being read: the first of `ids` whose box crosses the band just below the sticky header. */
export function useScrollSpy(ids: string[]): string | null {
  const [active, setActive] = useState<string | null>(null);
  const key = ids.join("|");

  useEffect(() => {
    const list = key ? key.split("|") : [];
    const targets = list.flatMap((id) => {
      const el = document.getElementById(id);
      return el ? [el] : [];
    });
    if (targets.length === 0 || typeof IntersectionObserver === "undefined") {
      return;
    }
    const visible = new Set<string>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) visible.add(entry.target.id);
          else visible.delete(entry.target.id);
        }
        const first = list.find((id) => visible.has(id));
        // Between two sections the last one stays marked.
        if (first) setActive(first);
      },
      { rootMargin: `-${stickyOffset() + 8}px 0px -55% 0px` },
    );
    for (const el of targets) observer.observe(el);
    // The last sections of a page cannot reach the top band: at the very bottom the last one is the one read.
    const atBottom = () => {
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) setActive(list[list.length - 1] ?? null);
    };
    window.addEventListener("scroll", atBottom, { passive: true });
    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", atBottom);
    };
  }, [key]);

  return active !== null && ids.includes(active) ? active : null;
}
