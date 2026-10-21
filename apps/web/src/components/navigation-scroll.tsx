"use client";

import { usePathname, useRouter } from "next/navigation";
import { startTransition, useEffect, useLayoutEffect, useRef } from "react";

import { planNavigation } from "@/lib/navigation-scroll";
import { scrollToSection } from "@/lib/scroll-to-section";

/** Fired when this component takes over a link, so the progress bar can show it is on its way. */
export const NAVIGATION_START = "navigation-scroll:start";

/** How long to wait for a late page (streamed content) to show the section the address names. */
const ANCHOR_WAIT_MS = 3000;

/** The one place that decides where a page starts after the address moved to another page (the
 * landing site, the CRM, the account and the console alike). Mounted once in the root layout.
 *
 * - A new page starts at the top, in the same moment its content swaps, so there is no second jump
 *   afterwards (Next.js keeps the old position when the new page's first block is still on screen).
 * - An address with `#id` goes to that section once it is on the page, landing below the sticky
 *   header and opening it if it is folded (one method for every anchor link, even from another page;
 *   a link to a section of another page is opened here, without Next.js's own jump, so the page
 *   glides there once instead of jumping and then correcting).
 * - Back and forward return to where the person was on that page.
 * - A window opening over a page, and closing again, leave the page where it is.
 * - A change that keeps the same page (a filter, a week, a sort) is not touched at all. */
export function NavigationScroll() {
  const pathname = usePathname();
  const router = useRouter();
  const previous = useRef(pathname);
  const under = useRef<string | null>(null);
  const traversal = useRef(false);
  const positions = useRef(new Map<string, number>());
  const here = useRef(pathname);
  const stopAnchor = useRef<(() => void) | null>(null);

  useEffect(() => {
    const onPop = () => {
      traversal.current = true;
    };
    // A click starts a fresh move; only back and forward count as a traversal.
    const onClick = () => {
      traversal.current = false;
    };
    const onAnchorLink = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = (event.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || (link.target && link.target !== "_self") || link.hasAttribute("download")) return;
      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin || !url.hash || url.pathname === window.location.pathname) return;
      // The link's own click handlers still run; only its navigation is done here.
      event.preventDefault();
      window.dispatchEvent(new Event(NAVIGATION_START));
      startTransition(() => router.push(url.pathname + url.search + url.hash, { scroll: false }));
    };
    let frame = 0;
    const remember = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => positions.current.set(here.current, window.scrollY));
    };
    window.addEventListener("popstate", onPop);
    document.addEventListener("click", onClick, true);
    document.addEventListener("click", onAnchorLink, true);
    window.addEventListener("scroll", remember, { passive: true });
    return () => {
      window.removeEventListener("popstate", onPop);
      document.removeEventListener("click", onClick, true);
      document.removeEventListener("click", onAnchorLink, true);
      window.removeEventListener("scroll", remember);
      cancelAnimationFrame(frame);
    };
  }, [router]);

  useLayoutEffect(() => {
    if (previous.current === pathname) return;
    stopAnchor.current?.();
    stopAnchor.current = null;
    const { plan, under: nextUnder } = planNavigation({
      pathname,
      previous: previous.current,
      hash: window.location.hash,
      traversal: traversal.current,
      saved: positions.current.get(pathname),
      windowOpen: document.querySelector("dialog.modal-dialog") !== null,
      under: under.current,
    });
    previous.current = pathname;
    here.current = pathname;
    under.current = nextUnder;
    traversal.current = false;

    if (plan.kind === "top") {
      window.scrollTo({ top: 0, behavior: "instant" });
    } else if (plan.kind === "restore") {
      restore(plan.y);
    } else if (plan.kind === "anchor") {
      // Start from the top, so the glide to the section is short; the section may not be in the page yet.
      window.scrollTo({ top: 0, behavior: "instant" });
      stopAnchor.current = whenPresent(plan.id, (id) => {
        stopAnchor.current = scrollToSection(id);
      });
    }
  }, [pathname]);

  useEffect(() => () => stopAnchor.current?.(), []);
  return null;
}

/** Back to a saved position; the page may still be growing, so keep trying for a moment. */
function restore(y: number) {
  const started = performance.now();
  const step = () => {
    window.scrollTo({ top: y, behavior: "instant" });
    const reached = Math.abs(window.scrollY - y) < 2;
    if (!reached && performance.now() - started < 1000) requestAnimationFrame(step);
  };
  step();
}

/** Runs `then` once an element with `id` exists (immediately if it already does); returns a cancel. */
function whenPresent(id: string, then: (id: string) => void): () => void {
  let cancelled = false;
  const started = performance.now();
  const check = () => {
    if (cancelled) return;
    if (document.getElementById(id)) {
      then(id);
      return;
    }
    if (performance.now() - started < ANCHOR_WAIT_MS) requestAnimationFrame(check);
  };
  // After the commit, so Next.js's own scroll to the anchor has already happened.
  requestAnimationFrame(check);
  return () => {
    cancelled = true;
  };
}
