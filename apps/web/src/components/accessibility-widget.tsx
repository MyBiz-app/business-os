"use client";

import { Accessibility, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { AccessibilitySettings, resetAccessibility } from "@/components/accessibility";
import { useDismiss } from "@/components/use-dismiss";

/** The floating accessibility button every public page and sign-in screen carries: language, day or night,
 * contrast, text size and motion in one panel, plus the accessibility statement. */
export function AccessibilityWidget() {
  const t = useTranslations("accessibility");
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, root, trigger);

  // The button can be dragged out of the way (position kept for the visit) or hidden with the small X.
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const [hidden, setHidden] = useState(false);
  const drag = useRef<{ dx: number; dy: number; moved: boolean } | null>(null);
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem("a11y-widget");
      if (saved === "hidden") setHidden(true);
      else if (saved) setPos(JSON.parse(saved));
    } catch {}
  }, []);
  const clamp = (x: number, y: number) => ({
    x: Math.min(Math.max(8, x), window.innerWidth - 64),
    y: Math.min(Math.max(8, y), window.innerHeight - 64),
  });
  const onDown = (event: React.PointerEvent<HTMLButtonElement>) => {
    const rect = root.current!.getBoundingClientRect();
    drag.current = { dx: event.clientX - rect.left, dy: event.clientY - rect.top, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const onMove = (event: React.PointerEvent<HTMLButtonElement>) => {
    const d = drag.current;
    if (!d) return;
    const next = clamp(event.clientX - d.dx, event.clientY - d.dy);
    const rect = root.current!.getBoundingClientRect();
    if (!d.moved && Math.hypot(next.x - rect.left, next.y - rect.top) < 6) return;
    d.moved = true;
    setPos(next);
  };
  const onUp = () => {
    if (drag.current?.moved && pos) {
      try { sessionStorage.setItem("a11y-widget", JSON.stringify(pos)); } catch {}
    }
  };
  if (hidden) return null;
  const onLeft = pos ? pos.x < window.innerWidth / 2 : true;
  const onTop = pos ? pos.y < window.innerHeight / 2 : false;

  return (
    <div
      ref={root}
      style={pos ? { left: pos.x, top: pos.y } : undefined}
      className={`fixed z-40 touch-none print:hidden ${pos ? "" : "bottom-5 start-5"}`}
    >
      <button
        type="button"
        onClick={() => { try { sessionStorage.setItem("a11y-widget", "hidden"); } catch {} setHidden(true); }}
        aria-label={t("widgetHide")}
        className="absolute -end-1 -top-1 z-10 flex size-5 items-center justify-center rounded-full bg-black text-white"
      >
        <X aria-hidden="true" className="size-3" />
      </button>
      {open && (
        <section
          id={panelId}
          role="dialog"
          aria-label={t("widgetTitle")}
          className={`popover absolute ${onTop ? "top-16" : "bottom-16"} ${onLeft ? "start-0" : "end-0"} flex max-h-[70vh] w-[min(24rem,calc(100vw-2.5rem))] flex-col gap-4 overflow-y-auto p-5`}
          data-open="true"
        >
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-bold">{t("widgetTitle")}</h2>
            <button type="button" onClick={() => { close(); trigger.current?.focus(); }} aria-label={t("widgetClose")} className="btn-ghost size-8">
              <X aria-hidden="true" className="size-4" />
            </button>
          </div>
          <AccessibilitySettings />
          <div className="flex items-center justify-between gap-3 border-t border-border pt-4 text-sm">
            <button type="button" onClick={resetAccessibility} className="font-semibold text-primary hover:underline">
              {t("reset")}
            </button>
            <Link href="/legal/accessibility" className="font-semibold text-primary hover:underline">
              {t("statement")}
            </Link>
          </div>
        </section>
      )}
      <button
        ref={trigger}
        type="button"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={t("widgetOpen")}
        title={t("widgetOpen")}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onClick={() => { if (drag.current?.moved) { drag.current = null; return; } setOpen((value) => !value); }}
        className="flex size-14 items-center justify-center rounded-full bg-primary text-on-primary shadow-lg shadow-primary/30 ring-4 ring-white/70 transition-transform duration-200 hover:scale-105 active:scale-95 dark:ring-black/40"
      >
        <Accessibility aria-hidden="true" className="size-7" />
      </button>
    </div>
  );
}
