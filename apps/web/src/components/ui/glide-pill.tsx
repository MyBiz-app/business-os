"use client";

import { type RefObject, useLayoutEffect, useState } from "react";

type Box = { x: number; y: number; width: number; height: number };

/** Where the marked item of a menu sits, measured from the menu's own corner (so it stays right
 * while the menu itself scrolls), and whether the pill may glide there yet. The first placement is
 * instant: only a change after that glides. `selector` finds the marked item inside `root`; with
 * several matches the last one wins (the deepest, when an item and its sub-item are both marked). */
export function useGlide(root: RefObject<HTMLElement | null>, selector: string): { box: Box | null; glide: boolean } {
  const [box, setBox] = useState<Box | null>(null);
  const [glide, setGlide] = useState(false);

  // Runs after every render: a menu changes shape when a group unfolds or the marked item moves.
  useLayoutEffect(() => {
    const element = root.current;
    if (!element) return;
    function measure() {
      const found = Array.from(element?.querySelectorAll<HTMLElement>(selector) ?? []);
      const target = found.reverse().find((candidate) => candidate.offsetParent !== null);
      // Hidden (a collapsed phone menu) or nothing marked: no pill.
      if (!element || !target) {
        setBox((now) => (now === null ? now : null));
        return;
      }
      const a = element.getBoundingClientRect();
      const b = target.getBoundingClientRect();
      const next = { x: b.left - a.left + element.scrollLeft, y: b.top - a.top + element.scrollTop, width: b.width, height: b.height };
      setBox((now) => (now && now.x === next.x && now.y === next.y && now.width === next.width && now.height === next.height ? now : next));
    }
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  });

  useLayoutEffect(() => {
    if (!box || glide) return;
    const frame = requestAnimationFrame(() => setGlide(true));
    return () => cancelAnimationFrame(frame);
  }, [box, glide]);

  return { box, glide };
}

/** The soft marker behind the current item of a menu. It glides (200ms, easing out) from the item
 * you left to the one you reached, so the eye follows where it went. Put it first inside a
 * `position: relative` menu, and give the items a transparent background. */
export function GlidePill({ box, glide, className = "", children }: { box: Box | null; glide: boolean; className?: string; children?: React.ReactNode }) {
  if (!box) return null;
  return (
    <span
      aria-hidden="true"
      data-glide={glide || undefined}
      className={`glide-pill ${className}`}
      style={{ width: box.width, height: box.height, transform: `translate(${box.x}px, ${box.y}px)` }}
    >
      {children}
    </span>
  );
}
