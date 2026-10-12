"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

const MIN_GAP_MS = 15_000; // never refresh twice within this, whatever fires
const IDLE_AFTER_MS = 5 * 60_000; // no clicks, keys or scrolls for this long: stop polling

/** Keeps a shared screen current (decision X24): reloads its data when the tab comes back into
 * view and every `seconds` while somebody is actually using it. Each refresh re-runs the page's
 * server work (its API calls), so it is skipped when the tab is hidden or offline, and polling
 * stops after a few idle minutes (it resumes on the next touch or when the tab is focused). The
 * page itself stays where it is. */
export function LiveRefresh({ seconds = 60 }: { seconds?: number }) {
  const router = useRouter();
  useEffect(() => {
    let last = Date.now();
    let active = Date.now();
    const refresh = (force: boolean) => {
      if (document.visibilityState !== "visible" || navigator.onLine === false) return;
      const now = Date.now();
      if (now - last < MIN_GAP_MS) return;
      if (!force && now - active > IDLE_AFTER_MS) return; // idle: the timer just skips
      last = now;
      router.refresh();
    };
    const touch = () => {
      active = Date.now();
    };
    const back = () => {
      touch();
      refresh(true);
    };
    const timer = window.setInterval(() => refresh(false), seconds * 1000);
    const touches = ["pointerdown", "keydown", "scroll"] as const;
    for (const name of touches) window.addEventListener(name, touch, { passive: true });
    document.addEventListener("visibilitychange", back);
    window.addEventListener("focus", back);
    window.addEventListener("online", back);
    return () => {
      window.clearInterval(timer);
      for (const name of touches) window.removeEventListener(name, touch);
      document.removeEventListener("visibilitychange", back);
      window.removeEventListener("focus", back);
      window.removeEventListener("online", back);
    };
  }, [router, seconds]);
  return null;
}
