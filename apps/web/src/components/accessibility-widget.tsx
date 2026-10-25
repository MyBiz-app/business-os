"use client";

import { Accessibility, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState, useSyncExternalStore } from "react";

import { AccessibilitySettings, resetAccessibility } from "@/components/accessibility";
import { useDismiss } from "@/components/use-dismiss";

const SIZE = 48;
const MARGIN = 8;
const DRAG_THRESHOLD = 6;
const NUDGE = 16;
const PANEL_WIDTH = 384;
const POS_KEY = "a11y-widget-pos";
const HIDDEN_KEY = "a11y-widget-hidden";

type Pos = { x: number; y: number };

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

const CHANGE_EVENT = "a11y-widget-change";

function writeStorage(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // private browsing: the choice still applies until the page is closed
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function subscribe(notify: () => void) {
  window.addEventListener("storage", notify);
  window.addEventListener(CHANGE_EVENT, notify);
  window.addEventListener("resize", notify);
  return () => {
    window.removeEventListener("storage", notify);
    window.removeEventListener(CHANGE_EVENT, notify);
    window.removeEventListener("resize", notify);
  };
}

const noopSubscribe = () => () => {};

function clamp(pos: Pos): Pos {
  const maxX = Math.max(MARGIN, window.innerWidth - SIZE - MARGIN);
  const maxY = Math.max(MARGIN, window.innerHeight - SIZE - MARGIN);
  return { x: Math.min(Math.max(pos.x, MARGIN), maxX), y: Math.min(Math.max(pos.y, MARGIN), maxY) };
}

function parsePos(raw: string | null): Pos | null {
  try {
    if (!raw) return null;
    const value = JSON.parse(raw);
    return typeof value?.x === "number" && typeof value?.y === "number" ? clamp(value) : null;
  } catch {
    return null;
  }
}

/** Brings back the floating button after the visitor closed it (used by the footer). */
export function showAccessibilityWidget() {
  writeStorage(HIDDEN_KEY, null);
}

/** The floating accessibility button every public page and sign-in screen carries: language, day or night,
 * contrast, text size and motion in one panel, plus the accessibility statement. The visitor can drag it out
 * of the way (mouse, touch or arrow keys) and close it with the small x; both choices stay on this device. */
export function AccessibilityWidget() {
  const t = useTranslations("accessibility");
  const [open, setOpen] = useState(false);
  const ready = useSyncExternalStore(noopSubscribe, () => true, () => false);
  const hidden = useSyncExternalStore(subscribe, () => readStorage(HIDDEN_KEY) === "1", () => true);
  const storedPos = useSyncExternalStore(subscribe, () => readStorage(POS_KEY), () => null);
  const [dragPos, setDragPos] = useState<Pos | null>(null);
  const saved = ready ? parsePos(storedPos) : null;
  const pos = dragPos ?? saved;
  const [panelStyle, setPanelStyle] = useState<React.CSSProperties>({});
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const drag = useRef<{ id: number; startX: number; startY: number; originX: number; originY: number; moved: boolean } | null>(null);
  const panelId = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, root, trigger);

  // The panel is fixed to the viewport and placed from the button's rectangle: it opens toward the side with
  // more room (so it never leaves the screen, in LTR or RTL) and is re-placed on resize and when the button moves.
  useEffect(() => {
    if (!open) return;
    const place = () => {
      const button = trigger.current;
      if (!button) return;
      const rect = button.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const width = Math.min(PANEL_WIDTH, vw - 2 * MARGIN);
      const alignRight = rect.left + rect.width / 2 > vw / 2;
      const left = Math.min(Math.max(alignRight ? rect.right - width : rect.left, MARGIN), vw - width - MARGIN);
      const spaceBelow = vh - rect.bottom - MARGIN * 2;
      const spaceAbove = rect.top - MARGIN * 2;
      const below = spaceBelow >= spaceAbove;
      const maxHeight = Math.max(160, Math.min(vh * 0.7, below ? spaceBelow : spaceAbove));
      setPanelStyle(
        below
          ? { left, width, maxHeight, top: rect.bottom + MARGIN }
          : { left, width, maxHeight, bottom: vh - rect.top + MARGIN },
      );
    };
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [open, pos?.x, pos?.y]);

  const move = (next: Pos) => {
    writeStorage(POS_KEY, JSON.stringify(clamp(next)));
    setDragPos(null);
  };

  const onPointerDown = (event: React.PointerEvent<HTMLButtonElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    drag.current = { id: event.pointerId, startX: event.clientX, startY: event.clientY, originX: rect.left, originY: rect.top, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent<HTMLButtonElement>) => {
    const state = drag.current;
    if (!state || state.id !== event.pointerId) return;
    const dx = event.clientX - state.startX;
    const dy = event.clientY - state.startY;
    if (!state.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
    if (!state.moved) {
      state.moved = true;
      setOpen(false);
    }
    setDragPos(clamp({ x: state.originX + dx, y: state.originY + dy }));
  };

  const onPointerUp = (event: React.PointerEvent<HTMLButtonElement>) => {
    const state = drag.current;
    if (!state || state.id !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (state.moved) {
      const dx = event.clientX - state.startX;
      const dy = event.clientY - state.startY;
      move({ x: state.originX + dx, y: state.originY + dy });
      // The click that follows a drag must not toggle the panel.
      window.setTimeout(() => {
        drag.current = null;
      }, 0);
    } else {
      drag.current = null;
    }
  };

  const onClick = () => {
    if (drag.current?.moved) return;
    setOpen((value) => !value);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    const step: Record<string, Pos> = {
      ArrowLeft: { x: -NUDGE, y: 0 },
      ArrowRight: { x: NUDGE, y: 0 },
      ArrowUp: { x: 0, y: -NUDGE },
      ArrowDown: { x: 0, y: NUDGE },
    };
    const delta = step[event.key];
    if (!delta || !trigger.current) return;
    event.preventDefault();
    const rect = trigger.current.getBoundingClientRect();
    setOpen(false);
    move({ x: rect.left + delta.x, y: rect.top + delta.y });
  };

  const dismiss = () => {
    setOpen(false);
    writeStorage(HIDDEN_KEY, "1");
  };

  if (!ready || hidden) return null;

  const placed = pos ? { left: pos.x, top: pos.y } : undefined;

  return (
    <div
      ref={root}
      className={pos ? "fixed z-40 print:hidden" : "fixed bottom-5 start-5 z-40 print:hidden"}
      style={placed}
    >
      {open && (
        <section
          id={panelId}
          role="dialog"
          aria-label={t("widgetTitle")}
          style={panelStyle}
          className="popover fixed flex flex-col gap-4 overflow-y-auto p-5"
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
            <button type="button" onClick={resetAccessibility} className="btn-link font-semibold text-primary-ink hover:underline">
              {t("reset")}
            </button>
            <Link href="/legal/accessibility" className="font-semibold text-primary-ink hover:underline">
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
        aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight"
        title={t("widgetDrag")}
        onClick={onClick}
        onKeyDown={onKeyDown}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        style={{ touchAction: "none" }}
        className="btn-plain flex size-12 cursor-grab touch-none items-center justify-center rounded-full bg-primary text-on-primary shadow-lg shadow-primary/30 ring-2 ring-white/70 transition-transform duration-200 hover:scale-105 active:scale-95 active:cursor-grabbing md:size-14 md:ring-4 dark:ring-black/40"
      >
        <Accessibility aria-hidden="true" className="size-6 md:size-7" />
      </button>
      <button
        type="button"
        onClick={dismiss}
        aria-label={t("widgetHide")}
        title={t("widgetHide")}
        className="btn-icon absolute -end-1.5 -top-1.5 flex size-6 min-h-0! min-w-0! items-center justify-center rounded-full bg-black/80 text-white shadow-md ring-1 ring-white/80 hover:bg-navy md:-end-2 md:-top-2 md:size-7 md:ring-2"
      >
        <X aria-hidden="true" className="size-3 md:size-3.5" />
      </button>
    </div>
  );
}
