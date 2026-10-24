"use client";

import { useTranslations } from "next-intl";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { NAVIGATION_START } from "@/components/navigation-scroll";

import { ProgressBar } from "./loading";

/** Only a navigation that takes longer than this shows the bar. */
const SHOW_AFTER_MS = 300;
/** Safety net: the bar never stays on for good if a navigation is cancelled. */
const GIVE_UP_MS = 20000;
/** A click that never became a page change (a link another handler took over) must not leave the page softened. */
const SOFTEN_MAX_MS = 6000;

/** A thin bar across the top of the window while a page change takes longer than 300ms (like
 * YouTube or GitHub). Next.js has no router events, so it starts when a link to another address on
 * this site is clicked and ends when the address (path or query) changes. Mounted once in the root
 * layout, inside a Suspense boundary (it reads the query string). */
export function RouteProgress() {
  const t = useTranslations("common");
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const [visible, setVisible] = useState(false);
  const showTimer = useRef<number | undefined>(undefined);
  const giveUpTimer = useRef<number | undefined>(undefined);
  const softTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    function stop() {
      delete document.documentElement.dataset.navigating;
      window.clearTimeout(softTimer.current);
      window.clearTimeout(showTimer.current);
      window.clearTimeout(giveUpTimer.current);
      setVisible(false);
    }
    function start() {
      stop();
      // The current page softens right away (see .site-page), so the swap is not a hard cut.
      document.documentElement.dataset.navigating = "";
      softTimer.current = window.setTimeout(() => delete document.documentElement.dataset.navigating, SOFTEN_MAX_MS);
      showTimer.current = window.setTimeout(() => setVisible(true), SHOW_AFTER_MS);
      giveUpTimer.current = window.setTimeout(stop, GIVE_UP_MS);
    }
    // Capture phase: Next.js's <Link> prevents the browser's own navigation in its click handler,
    // which runs before a bubbling listener on the document.
    function onClick(event: MouseEvent) {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = (event.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || (link.target && link.target !== "_self") || link.hasAttribute("download")) return;
      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin) return;
      // Same address (or only a #hash): the page does not change.
      if (url.pathname === window.location.pathname && url.search === window.location.search) return;
      start();
    }
    document.addEventListener("click", onClick, true);
    window.addEventListener("popstate", start);
    window.addEventListener(NAVIGATION_START, start);
    return () => {
      document.removeEventListener("click", onClick, true);
      window.removeEventListener("popstate", start);
      window.removeEventListener(NAVIGATION_START, start);
      window.clearTimeout(showTimer.current);
      window.clearTimeout(giveUpTimer.current);
      window.clearTimeout(softTimer.current);
    };
  }, []);

  // The address changed: the new page is here. The softening ends before the new page is first painted
  // (a layout effect), so the new page does not start dimmed.
  useLayoutEffect(() => {
    delete document.documentElement.dataset.navigating;
  }, [pathname, search]);
  useEffect(() => {
    window.clearTimeout(showTimer.current);
    window.clearTimeout(giveUpTimer.current);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setVisible(false);
  }, [pathname, search]);

  if (!visible) return null;
  return (
    <div className="route-progress">
      <ProgressBar label={t("loading")} />
    </div>
  );
}
