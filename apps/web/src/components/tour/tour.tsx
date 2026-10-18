"use client";

import { useTranslations } from "next-intl";
import { type ReactNode, useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";

import { Modal } from "@/components/ui/modal";

export type TourStep = {
  id: string;
  title: string;
  body: ReactNode;
  /** A `data-tour` value on the page. With it the step points at that element; without it the step is a window. */
  target?: string;
};

const selectorOf = (target: string) => `[data-tour="${target}"]`;
const GAP = 12;

/** A guided tour: windows that explain, and steps that point at a part of the page. Esc or the X
 * skips it, and focus goes back to the button that started it. Steps whose target is not on the
 * screen (a small phone hides some) are left out. `onClose` fires once, whether the tour was
 * finished or skipped. Mount it only while it should show. */
export function Tour({ steps, onClose }: { steps: readonly TourStep[]; onClose: () => void }) {
  const t = useTranslations("tour");
  const opener = useRef<HTMLElement | null>(null);
  const [index, setIndex] = useState(0);
  const [available, setAvailable] = useState<readonly TourStep[] | null>(null);

  useEffect(() => {
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const timer = window.setTimeout(
      () => setAvailable(steps.filter((s) => !s.target || isShown(document.querySelector(selectorOf(s.target))))),
      0,
    );
    return () => window.clearTimeout(timer);
  }, [steps]);

  const close = useCallback(() => {
    onClose();
    const back = opener.current;
    if (back && document.contains(back)) window.setTimeout(() => back.focus(), 0);
  }, [onClose]);

  if (!available || available.length === 0) return null;
  const step = available[Math.min(index, available.length - 1)];
  const last = index >= available.length - 1;
  const nav = (
    <TourNav
      current={index + 1}
      total={available.length}
      last={last}
      onBack={index > 0 ? () => setIndex(index - 1) : undefined}
      onNext={() => (last ? close() : setIndex(index + 1))}
      onSkip={last ? undefined : close}
      labels={{ back: t("back"), next: t("next"), done: t("done"), skip: t("skip"), progress: t("progress", { current: index + 1, total: available.length }) }}
    />
  );

  return step.target ? (
    <Spotlight key={step.id} step={step} onClose={close}>
      {nav}
    </Spotlight>
  ) : (
    <Modal onClose={close} title={step.title} size="md" footer={nav}>
      <div className="flex flex-col gap-4 text-sm leading-relaxed">{step.body}</div>
    </Modal>
  );
}

function isShown(element: Element | null): boolean {
  if (!(element instanceof HTMLElement)) return false;
  const box = element.getBoundingClientRect();
  return box.width > 0 && box.height > 0;
}

type Labels = { back: string; next: string; done: string; skip: string; progress: string };

function TourNav({ current, total, last, onBack, onNext, onSkip, labels }: { current: number; total: number; last: boolean; onBack?: () => void; onNext: () => void; onSkip?: () => void; labels: Labels }) {
  return (
    <>
      <p className="me-auto text-xs text-muted">
        <span className="sr-only">{labels.progress}</span>
        <span aria-hidden="true" className="flex items-center gap-1.5">
          {Array.from({ length: total }, (_, i) => (
            <span key={i} className={`size-1.5 rounded-full ${i + 1 === current ? "bg-primary" : "bg-border"}`} />
          ))}
        </span>
      </p>
      {onSkip && (
        <button type="button" className="btn-plain px-3 py-2 text-sm text-muted hover:text-foreground" onClick={onSkip}>
          {labels.skip}
        </button>
      )}
      {onBack && (
        <button type="button" className="btn-secondary px-4 py-2 text-sm" onClick={onBack}>
          {labels.back}
        </button>
      )}
      <button type="button" className="btn-primary px-4 py-2 text-sm" onClick={onNext} autoFocus>
        {last ? labels.done : labels.next}
      </button>
    </>
  );
}

/** A step that points at an element: the rest of the page dims, a card sits next to the element. */
function Spotlight({ step, onClose, children }: { step: TourStep; onClose: () => void; children: ReactNode }) {
  const titleId = useId();
  const card = useRef<HTMLDivElement>(null);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [place, setPlace] = useState<{ top: number; left: number } | null>(null);

  const measure = useCallback(() => {
    const element = step.target ? document.querySelector(selectorOf(step.target)) : null;
    setRect(element ? element.getBoundingClientRect() : null);
  }, [step.target]);

  useLayoutEffect(() => {
    const element = step.target ? document.querySelector(selectorOf(step.target)) : null;
    element?.scrollIntoView({ block: "center", behavior: "instant" });
    const first = window.setTimeout(measure, 0);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.clearTimeout(first);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [step.target, measure]);

  // Below the element when there is room, above it otherwise; kept inside the screen.
  useLayoutEffect(() => {
    if (!rect || !card.current) return;
    const { offsetWidth: width, offsetHeight: height } = card.current;
    const below = rect.bottom + GAP + height <= window.innerHeight;
    const top = below ? rect.bottom + GAP : Math.max(GAP, rect.top - GAP - height);
    const left = Math.min(Math.max(GAP, rect.left + rect.width / 2 - width / 2), window.innerWidth - width - GAP);
    const timer = window.setTimeout(() => setPlace({ top, left }), 0);
    return () => window.clearTimeout(timer);
  }, [rect]);

  useEffect(() => {
    card.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const pad = 6;
  const hole = useMemo(
    () => (rect ? { top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 } : null),
    [rect],
  );

  return (
    <div className="fixed inset-0 z-50">
      {hole && <div aria-hidden="true" className="tour-hole" style={hole} />}
      <div
        ref={card}
        role="dialog"
        aria-modal="false"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="card absolute flex w-[min(22rem,calc(100vw-1.5rem))] flex-col gap-3 p-4 shadow-2xl outline-none"
        style={{ top: place?.top ?? 0, left: place?.left ?? 0, visibility: place ? "visible" : "hidden" }}
      >
        <h2 id={titleId} className="text-base font-bold leading-snug">
          {step.title}
        </h2>
        <div className="text-sm leading-relaxed">{step.body}</div>
        <div className="flex flex-wrap items-center justify-end gap-2">{children}</div>
      </div>
    </div>
  );
}
