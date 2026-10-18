"use client";

import { ChevronDown } from "lucide-react";
import { type ReactNode, useEffect, useId, useState } from "react";

const PREFIX = "section:";
/** Fired with a section id to open that section (used by section menus). */
export const OPEN_EVENT = "open-section";

function remembered(key: string | undefined): boolean | null {
  if (!key) return null;
  try {
    const value = window.localStorage.getItem(PREFIX + key);
    return value === null ? null : value === "1";
  } catch {
    return null;
  }
}

/** One foldable section: a title, an optional description line and an arrow at the start that
 * folds and unfolds it. With `storageKey` the choice is remembered per browser (the first section
 * is open by default, the rest as the person left them). Replaces the bare `<details>` blocks.
 *
 * `variant="inline"` is the light version for a "show all", an "add" form or a danger zone inside
 * a card: no frame of its own, just the arrow and the title as a button (`className` frames the
 * wrapper (on a card too: a tint or border), `triggerClassName` replaces the button's weight and colour, `bodyClassName` the content). */
export function CollapsibleSection({
  title,
  description,
  children,
  defaultOpen = false,
  storageKey,
  actions,
  icon,
  id,
  variant = "card",
  className,
  triggerClassName,
  bodyClassName,
}: {
  title: ReactNode;
  description?: string;
  children: ReactNode;
  defaultOpen?: boolean;
  storageKey?: string;
  /** Buttons shown at the end of the header line (not part of the fold button). */
  actions?: ReactNode;
  /** A small icon before the title. */
  icon?: ReactNode;
  /** Anchor of the section: a link to `#id` (or the section menu) opens it and scrolls to it. */
  id?: string;
  variant?: "card" | "inline";
  className?: string;
  triggerClassName?: string;
  bodyClassName?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const panel = useId();

  useEffect(() => {
    const saved = remembered(storageKey);
    // Read after mount so the server and first client render agree.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (saved !== null) setOpen(saved);
  }, [storageKey]);

  useEffect(() => {
    if (!id) return;
    const openIfTarget = () => {
      if (window.location.hash === `#${id}`) setOpen(true);
    };
    const openById = (event: Event) => {
      if ((event as CustomEvent<string>).detail === id) setOpen(true);
    };
    openIfTarget();
    window.addEventListener("hashchange", openIfTarget);
    window.addEventListener(OPEN_EVENT, openById);
    return () => {
      window.removeEventListener("hashchange", openIfTarget);
      window.removeEventListener(OPEN_EVENT, openById);
    };
  }, [id]);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (!storageKey) return;
    try {
      window.localStorage.setItem(PREFIX + storageKey, next ? "1" : "0");
    } catch {
      // Private mode or blocked storage: the section still works, it just is not remembered.
    }
  }

  if (variant === "inline") {
    return (
      <div id={id} className={className}>
        <button
          type="button"
          className={`btn-plain flex max-w-full items-center gap-1.5 text-start text-sm ${triggerClassName ?? "font-medium text-primary-ink"}`}
          aria-expanded={open}
          aria-controls={panel}
          onClick={toggle}
        >
          <ChevronDown aria-hidden="true" className="section-chevron size-4 shrink-0" data-open={open || undefined} />
          <span className="min-w-0">{title}</span>
        </button>
        <div id={panel} className="section-body" data-open={open || undefined} inert={!open}>
          <div className="min-h-0 overflow-hidden">
            <div className={bodyClassName ?? "pt-3"}>{children}</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <section id={id} className={`card scroll-mt-24 overflow-hidden ${className ?? ""}`}>
      <div className="flex items-center gap-3 pe-4">
        <button
          type="button"
          className="btn-plain flex min-w-0 flex-1 items-start gap-3 px-5 py-4 text-start"
          aria-expanded={open}
          aria-controls={panel}
          onClick={toggle}
        >
          <ChevronDown aria-hidden="true" className="section-chevron mt-0.5 size-5 shrink-0 text-muted" data-open={open || undefined} />
          <span className="min-w-0">
            <span className="flex items-center gap-2 font-semibold">
              {icon}
              {title}
            </span>
            {description ? <span className="mt-0.5 block text-sm text-muted">{description}</span> : null}
          </span>
        </button>
        {actions}
      </div>
      <div id={panel} className="section-body" data-open={open || undefined} inert={!open}>
        <div className="min-h-0 overflow-hidden">
          <div className="border-t border-border px-5 py-5">{children}</div>
        </div>
      </div>
    </section>
  );
}
