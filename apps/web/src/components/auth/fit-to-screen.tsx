"use client";

import { useLayoutEffect, useRef, useState } from "react";

/** Below this scale the text gets too small to read, so the form scrolls instead. */
const MIN_SCALE = 0.62;
/** Air kept above and below the form. */
const BREATHING_ROOM = 24;

/** Keeps a single-form screen inside the viewport: the form is centred, and when the window is
 * too short it shrinks to fit rather than scrolling. Without JavaScript, or below the minimum
 * scale, the area scrolls as a normal page would. */
export function FitToScreen({ children }: { children: React.ReactNode }) {
  const box = useRef<HTMLElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState<{ scale: number; height?: number }>({ scale: 1 });

  useLayoutEffect(() => {
    const boxEl = box.current;
    const contentEl = content.current;
    if (!boxEl || !contentEl) return;
    const measure = () => {
      // offsetHeight ignores transforms, so this is always the unscaled height.
      const natural = contentEl.offsetHeight;
      const available = boxEl.clientHeight - BREATHING_ROOM;
      const scale = natural > available && available > 0 ? Math.max(MIN_SCALE, available / natural) : 1;
      const height = scale < 1 ? Math.ceil(natural * scale) : undefined;
      setFit((previous) => (previous.scale === scale && previous.height === height ? previous : { scale, height }));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(boxEl);
    observer.observe(contentEl);
    return () => observer.disconnect();
  }, []);

  return (
    <main ref={box} className="flex min-h-0 flex-1 flex-col overflow-y-auto overflow-x-hidden px-5">
      <div className="enter m-auto w-full max-w-md shrink-0 py-3" style={fit.height === undefined ? undefined : { height: fit.height + 24 }}>
        <div ref={content} className="origin-top" style={fit.scale < 1 ? { transform: `scale(${fit.scale})` } : undefined}>
          {children}
        </div>
      </div>
    </main>
  );
}
