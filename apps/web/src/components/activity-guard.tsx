"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { ACTIVITY_COOKIE, INACTIVITY_LIMIT_MS } from "@/lib/mfa";

const THROTTLE_MS = 60_000;

/** Keeps the "last active" stamp the proxy reads, and leaves a page nobody touches for too long
 * (the proxy then signs the person out and sends them to the sign-in page). */
export function ActivityGuard() {
  const router = useRouter();
  useEffect(() => {
    let last = Date.now();
    let written = 0;
    const secure = window.location.protocol === "https:" ? "; secure" : "";
    const stamp = (now: number) => {
      written = now;
      document.cookie = `${ACTIVITY_COOKIE}=${now}; path=/; max-age=${60 * 60 * 24 * 30}; samesite=lax${secure}`;
    };
    const leaveIfIdle = (now: number) => {
      if (now - last <= INACTIVITY_LIMIT_MS) return false;
      router.push("/dashboard"); // the proxy sees the old stamp and signs out
      return true;
    };
    const touch = () => {
      const now = Date.now();
      if (leaveIfIdle(now)) return; // a sleeping laptop wakes up: don't refresh the stamp
      last = now;
      if (now - written > THROTTLE_MS) stamp(now);
    };
    const events = ["pointerdown", "keydown", "scroll", "touchstart"] as const;
    for (const name of events) window.addEventListener(name, touch, { passive: true });
    const timer = window.setInterval(() => leaveIfIdle(Date.now()), THROTTLE_MS);
    return () => {
      for (const name of events) window.removeEventListener(name, touch);
      window.clearInterval(timer);
    };
  }, [router]);
  return null;
}
