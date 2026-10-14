"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** Tilts the intro scene a little toward the pointer (--px / --py, -1..1). Does nothing for
 * reduced motion, on touch screens, or while the scene is off screen. */
export function IntroTilt({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const calm = () =>
      window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      document.documentElement.dataset.motion === "reduce";
    if (calm() || !window.matchMedia("(hover: hover)").matches) return;
    let frame = 0;
    const onMove = (event: PointerEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const box = element.getBoundingClientRect();
        if (box.bottom < 0 || box.top > window.innerHeight) return;
        const x = ((event.clientX - box.left) / box.width - 0.5) * 2;
        const y = ((event.clientY - box.top) / box.height - 0.5) * 2;
        element.style.setProperty("--px", Math.max(-1, Math.min(1, x)).toFixed(3));
        element.style.setProperty("--py", Math.max(-1, Math.min(1, y)).toFixed(3));
      });
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", onMove);
    };
  }, []);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
