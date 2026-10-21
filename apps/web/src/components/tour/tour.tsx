"use client";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";

import { registerTour } from "./tour-state";

export type TourStep = {
  id: string;
  title: string;
  body: ReactNode;
  /** A `data-tour` value on the page. With it the step points at that element; without it the step sits in the middle. */
  target?: string;
};

const selectorOf = (target: string) => `[data-tour="${target}"]`;
const GAP = 12;
const HOLE_PAD = 6;

type View = { width: number; height: number };
type Placed = { top: number; left: number };

/** A guided tour in one window: a single card that glides between "in the middle of the screen" and
 * "next to a part of the page" while the rest of the page dims. Skipping (the button, the X or Esc)
 * only closes it: the page stays where you were, and nothing is saved on the way that could send
 * you somewhere else. Steps whose target is not on the screen (a small phone hides some) are left
 * out. `onClose` fires once, whether the tour was finished or skipped. Mount it only while it
 * should show. */
export function Tour({ steps, onClose }: { steps: readonly TourStep[]; onClose: () => void }) {
  const t = useTranslations("tour");
  const tCommon = useTranslations("common");
  const titleId = useId();
  const layer = useRef<HTMLDialogElement>(null);
  const card = useRef<HTMLDivElement>(null);
  const next = useRef<HTMLButtonElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const startScroll = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const closed = useRef(false);
  const [index, setIndex] = useState(0);
  const [available, setAvailable] = useState<readonly TourStep[] | null>(null);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [view, setView] = useState<View>({ width: 0, height: 0 });
  const [size, setSize] = useState<View | null>(null);
  const [placed, setPlaced] = useState<Placed | null>(null);
  const [glide, setGlide] = useState(false);

  // Other windows (the system messages) wait while a tour is open.
  useLayoutEffect(() => registerTour(), []);

  useEffect(() => {
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    startScroll.current = { x: window.scrollX, y: window.scrollY };
    const timer = window.setTimeout(
      () => setAvailable(steps.filter((s) => !s.target || isShown(document.querySelector(selectorOf(s.target))))),
      0,
    );
    return () => window.clearTimeout(timer);
  }, [steps]);

  const ready = available !== null && available.length > 0;
  useLayoutEffect(() => {
    const element = layer.current;
    if (!ready || !element) return;
    if (!element.open) element.showModal();
    return () => {
      if (element.open) element.close();
    };
  }, [ready]);

  const close = useCallback(() => {
    if (closed.current) return;
    closed.current = true;
    onClose();
    const back = opener.current;
    const { x, y } = startScroll.current;
    // After the window is gone: focus and scroll go back to where they were, without a jump.
    window.setTimeout(() => {
      if (back && document.contains(back)) back.focus({ preventScroll: true });
      window.scrollTo({ left: x, top: y, behavior: "instant" });
    }, 0);
  }, [onClose]);

  const step = ready ? available[Math.min(index, available.length - 1)] : null;
  const target = step?.target;

  const measure = useCallback(() => {
    const element = target ? document.querySelector(selectorOf(target)) : null;
    setRect(element ? element.getBoundingClientRect() : null);
    setView({ width: window.innerWidth, height: window.innerHeight });
  }, [target]);

  // A new step: bring its part of the page into view, then follow it while the page changes size.
  useLayoutEffect(() => {
    if (!ready) return;
    const element = target ? document.querySelector(selectorOf(target)) : null;
    if (element) {
      // A part that fits next to the card is centered; a tall one (the map) starts at the top.
      const roomy = element.getBoundingClientRect().height + (size?.height ?? 280) + GAP * 3 < window.innerHeight;
      element.scrollIntoView({ block: roomy ? "center" : "start", behavior: "instant" });
    }
    const first = window.setTimeout(measure, 0);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.clearTimeout(first);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
    // The card's height only matters for the first choice of scroll position.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, target, measure]);

  useLayoutEffect(() => {
    const element = card.current;
    if (!element) return;
    const observer = new ResizeObserver(() => setSize({ width: element.offsetWidth, height: element.offsetHeight }));
    observer.observe(element);
    return () => observer.disconnect();
  }, [ready]);

  // Where the card sits: in the middle, or next to the part it explains, kept inside the screen.
  useLayoutEffect(() => {
    if (!size || view.width === 0) return;
    const { width, height } = size;
    let top: number;
    let left: number;
    if (!rect) {
      top = (view.height - height) / 2;
      left = (view.width - width) / 2;
    } else {
      const below = view.height - rect.bottom - HOLE_PAD - GAP;
      const above = rect.top - HOLE_PAD - GAP;
      if (height <= below) top = rect.bottom + HOLE_PAD + GAP;
      else if (height <= above) top = rect.top - HOLE_PAD - GAP - height;
      else top = view.height - height - GAP; // a part as tall as the screen: the card sits on its lower edge
      left = rect.left + rect.width / 2 - width / 2;
    }
    const next = {
      top: Math.max(GAP, Math.min(top, view.height - height - GAP)),
      left: Math.max(GAP, Math.min(left, view.width - width - GAP)),
    };
    const timer = window.setTimeout(() => setPlaced(next), 0);
    return () => window.clearTimeout(timer);
  }, [rect, size, view]);

  // Moves are animated only once the card has its first place, so it does not fly in from a corner.
  useEffect(() => {
    if (!placed || glide) return;
    const frame = window.requestAnimationFrame(() => setGlide(true));
    return () => window.cancelAnimationFrame(frame);
  }, [placed, glide]);

  // The button that was pressed may be gone on the next step (Back on the first one): keep focus in the card.
  useEffect(() => {
    const active = document.activeElement;
    if (!ready || (active && card.current?.contains(active))) return;
    next.current?.focus({ preventScroll: true });
  }, [ready, index]);

  const hole = useMemo(() => {
    if (!rect) return { top: view.height / 2, left: view.width / 2, width: 0, height: 0 };
    return { top: rect.top - HOLE_PAD, left: rect.left - HOLE_PAD, width: rect.width + HOLE_PAD * 2, height: rect.height + HOLE_PAD * 2 };
  }, [rect, view]);

  if (!available || available.length === 0 || !step) return null;
  const last = index >= available.length - 1;
  return (
    <dialog
      ref={layer}
      className="tour-layer"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
    >
      <div aria-hidden="true" className="tour-hole" data-centered={rect ? undefined : ""} style={hole} />
      <div
        ref={card}
        className="card tour-card"
        data-glide={glide ? "" : undefined}
        style={{ top: placed?.top ?? 0, left: placed?.left ?? 0, opacity: placed ? 1 : 0 }}
      >
        <button type="button" className="btn-icon absolute end-2 top-2" aria-label={tCommon("closeDialog")} onClick={close}>
          <X aria-hidden="true" className="size-5" />
        </button>
        <div key={step.id} className="tour-step flex flex-col gap-3">
          <h2 id={titleId} className="pe-8 text-base font-bold leading-snug">
            {step.title}
          </h2>
          <div className="flex flex-col gap-3 text-sm leading-relaxed">{step.body}</div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <p className="me-auto text-xs text-muted">
            <span className="sr-only">{t("progress", { current: index + 1, total: available.length })}</span>
            <span aria-hidden="true" className="flex items-center gap-1.5">
              {available.map((s, i) => (
                <span key={s.id} className={`size-1.5 rounded-full transition-colors ${i === index ? "bg-primary" : "bg-border"}`} />
              ))}
            </span>
          </p>
          {!last && (
            <button type="button" className="btn-plain px-3 py-2 text-sm text-muted hover:text-foreground" onClick={close}>
              {t("skip")}
            </button>
          )}
          {index > 0 && (
            <button type="button" className="btn-secondary px-4 py-2 text-sm" onClick={() => setIndex(index - 1)}>
              {t("back")}
            </button>
          )}
          <button ref={next} type="button" className="btn-primary px-4 py-2 text-sm" autoFocus onClick={() => (last ? close() : setIndex(index + 1))}>
            {last ? t("done") : t("next")}
          </button>
        </div>
      </div>
    </dialog>
  );
}

function isShown(element: Element | null): boolean {
  if (!(element instanceof HTMLElement)) return false;
  const box = element.getBoundingClientRect();
  return box.width > 0 && box.height > 0;
}
