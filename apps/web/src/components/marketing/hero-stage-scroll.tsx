"use client";

import { useEffect } from "react";

const STEPS = 4;

/**
 * Drives the pinned hero scene. One passive scroll listener (only while the scene is on screen)
 * writes the scene's progress to a CSS variable (--p, 0..1) and the active step to data-step; all
 * the motion is CSS computed from --p, so React never re-renders while scrolling. Renders nothing.
 * Reduced motion leaves the scene in its static layout.
 */
export function HeroStageScroll({ targetId }: { targetId: string }) {
  useEffect(() => {
    const el = document.getElementById(targetId);
    if (!el) return;
    const still = () =>
      window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      document.documentElement.dataset.motion === "reduce";
    if (still()) return;

    let frame = 0;
    const update = () => {
      frame = 0;
      const rect = el.getBoundingClientRect();
      const span = rect.height - window.innerHeight;
      const p = span > 0 ? Math.min(1, Math.max(0, -rect.top / span)) : 0;
      el.style.setProperty("--p", p.toFixed(3));
      const step = String(Math.min(STEPS - 1, Math.floor(p * STEPS)));
      if (el.dataset.step !== step) el.dataset.step = step;
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };

    let listening = false;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting && !listening) {
        listening = true;
        window.addEventListener("scroll", onScroll, { passive: true });
        window.addEventListener("resize", onScroll);
        update();
      } else if (!entry?.isIntersecting && listening) {
        listening = false;
        window.removeEventListener("scroll", onScroll);
        window.removeEventListener("resize", onScroll);
      }
    });
    observer.observe(el);
    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [targetId]);

  return null;
}
