import { OPEN_EVENT } from "@/components/ui/collapsible-section";

/** How far down the viewport the sticky chrome reaches: the app header, plus the section bar when it spans the width (narrow screens). */
export function stickyOffset(): number {
  let bottom = 0;
  for (const el of document.querySelectorAll<HTMLElement>("header, .section-nav")) {
    const style = getComputedStyle(el);
    if (style.position !== "sticky" && style.position !== "fixed") continue;
    const rect = el.getBoundingClientRect();
    // The wide-screen menu is a column beside the content and covers nothing.
    if (rect.width < window.innerWidth * 0.6 || rect.height === 0) continue;
    // Where the bar will sit once stuck, whether or not the page has scrolled to that point yet.
    bottom = Math.max(bottom, (parseFloat(style.top) || 0) + rect.height);
  }
  return Math.round(bottom);
}

const ease = (t: number) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);

let stop: (() => void) | null = null;

/**
 * Scroll so the section's top edge lands just below the sticky chrome, with a small gap. Unfolds a
 * folded section first, then follows the target frame by frame, so the unfolding and late layout
 * (content that loads in) cannot leave it cut off. Stops at once when the person scrolls. Returns
 * a function that cancels it; `onDone` runs when it settles or is interrupted.
 */
export function scrollToSection(id: string, onDone?: () => void): () => void {
  stop?.();
  const el = document.getElementById(id);
  if (!el) {
    onDone?.();
    return () => {};
  }
  window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: id }));
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const gap = 16;
  const target = () => Math.max(0, Math.round(el.getBoundingClientRect().top + window.scrollY - stickyOffset() - gap));
  const from = window.scrollY;
  const duration = calm ? 0 : 450;
  const settleFor = 700;
  const started = performance.now();
  let frame = 0;
  let finished = false;

  const finish = () => {
    if (finished) return;
    finished = true;
    cancelAnimationFrame(frame);
    for (const type of ["wheel", "touchstart", "keydown", "mousedown"]) window.removeEventListener(type, finish);
    if (stop === cancel) stop = null;
    onDone?.();
  };
  const cancel = finish;
  for (const type of ["wheel", "touchstart", "keydown", "mousedown"]) window.addEventListener(type, finish, { passive: true });

  const tick = (now: number) => {
    const elapsed = now - started;
    const progress = duration === 0 ? 1 : Math.min(1, elapsed / duration);
    const goal = target();
    window.scrollTo({ top: progress >= 1 ? goal : from + (goal - from) * ease(progress), behavior: "instant" });
    // Keep correcting after arrival while the unfolding and late content settle.
    if (elapsed < duration + settleFor) frame = requestAnimationFrame(tick);
    else finish();
  };
  frame = requestAnimationFrame(tick);
  stop = cancel;
  return cancel;
}
