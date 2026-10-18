"use client";

import { useTranslations } from "next-intl";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ProgressBar } from "./loading";

/** Only a navigation that takes longer than this shows the bar. */
const SHOW_AFTER_MS = 300;
/** Safety net: the bar never stays on for good if a navigation is cancelled. */
const GIVE_UP_MS = 20000;

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

  useEffect(() => {
    function stop() {
      window.clearTimeout(showTimer.current);
      window.clearTimeout(giveUpTimer.current);
      setVisible(false);
    }
    function start() {
      stop();
      showTimer.current = window.setTimeout(() => setVisible(true), SHOW_AFTER_MS);
      giveUpTimer.current = window.setTimeout(stop, GIVE_UP_MS);
    }
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
    document.addEventListener("click", onClick);
    window.addEventListener("popstate", start);
    return () => {
      document.removeEventListener("click", onClick);
      window.removeEventListener("popstate", start);
      window.clearTimeout(showTimer.current);
      window.clearTimeout(giveUpTimer.current);
    };
  }, []);

  // The address changed: the new page is here.
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
