"use client";

import { type KeyboardEvent, type ReactNode, useCallback, useEffect, useId, useState } from "react";

import { type Placement, type PopoverPosition, computePopoverPosition } from "@/lib/popover-position";

import { cx } from "./cx";

/** What a trigger element needs to open and close a popover. Spread it on a `Button`, `IconButton`
 * or any element that can take focus. */
export type PopoverTriggerProps = {
  ref: (element: HTMLElement | null) => void;
  onClick: () => void;
  onKeyDown: (event: KeyboardEvent<HTMLElement>) => void;
  "aria-haspopup": "menu" | "dialog";
  "aria-expanded": boolean;
  "aria-controls": string;
};

const CLOSE_MS = 170; // a little longer than the 160ms fade of `.floating-panel`

type Props = {
  trigger: (props: PopoverTriggerProps) => ReactNode;
  /** The panel's content, or a function that receives `close`. */
  children: ReactNode | ((api: { close: () => void }) => ReactNode);
  /** The panel's name for screen readers. */
  label: string;
  /** Where the panel opens. start / end follow the reading direction (right edge first in Hebrew). */
  placement?: Placement;
  /** "dialog" for content (a form, a list of options); "menu" for a list of actions (see `Menu`). */
  role?: "dialog" | "menu";
  /** Width and padding of the panel (for example `w-72 p-3`). */
  className?: string;
  onKeyDown?: (event: KeyboardEvent<HTMLDivElement>) => void;
};

/** The one floating panel of the product. It is a native top-layer element positioned by
 * `computePopoverPosition` (opens on the preferred side, flips when it does not fit, stays inside
 * the screen, follows the page's direction), so every menu and popover opens the same way and is
 * never clipped by a parent. A click outside and Esc close it (Esc returns focus to the trigger). */
export function Popover({ trigger, children, label, placement = "bottom-start", role = "dialog", className, onKeyDown }: Props) {
  const id = useId();
  // The elements are state, not refs, so the render-prop functions below never read a ref.
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [panel, setPanel] = useState<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState(false);
  const [focusFirst, setFocusFirst] = useState(false);
  const [position, setPosition] = useState<(PopoverPosition & { rtl: boolean }) | null>(null);

  const close = useCallback(() => {
    setOpen(false);
    setShown(false);
    setFocusFirst(false);
  }, []);

  const place = useCallback(() => {
    if (!anchor || !panel) return;
    const rect = anchor.getBoundingClientRect();
    const rtl = getComputedStyle(anchor).direction === "rtl";
    const next = computePopoverPosition({
      anchor: { left: rect.left, top: rect.top, width: rect.width, height: rect.height },
      panel: { width: panel.offsetWidth, height: panel.offsetHeight },
      viewport: { width: document.documentElement.clientWidth, height: window.innerHeight },
      placement,
      rtl,
    });
    setPosition((now) => (now && now.left === next.left && now.top === next.top && now.placement === next.placement && now.rtl === rtl ? now : { ...next, rtl }));
  }, [anchor, panel, placement]);

  // Opening: into the top layer, then placed and faded in.
  useEffect(() => {
    if (!open || !panel) return;
    if (!panel.matches(":popover-open")) panel.showPopover();
    // Placed in the next frame (the panel is laid out but still transparent), together with the fade-in.
    const frame = requestAnimationFrame(() => {
      place();
      setShown(true);
    });
    // The page may scroll or resize while it is open; the panel follows its trigger.
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, panel, place]);

  // Closing: after the fade, out of the top layer. Opening again cancels it (the cleanup).
  useEffect(() => {
    if (open || !panel) return;
    const timer = window.setTimeout(() => {
      if (panel.matches(":popover-open")) panel.hidePopover();
      setPosition(null);
    }, CLOSE_MS);
    return () => window.clearTimeout(timer);
  }, [open, panel]);

  // Opened with the arrow keys: the first item takes focus once the panel is visible.
  useEffect(() => {
    if (shown && focusFirst) panel?.querySelector<HTMLElement>("[role=menuitem]:not([disabled])")?.focus();
  }, [shown, focusFirst, panel]);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Node;
      if (panel?.contains(target) || anchor?.contains(target)) return;
      close();
    };
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key !== "Escape") return;
      // Esc closes this panel only, not a window it may sit in.
      event.preventDefault();
      close();
      anchor?.focus();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close, panel, anchor]);

  const triggerProps: PopoverTriggerProps = {
    ref: setAnchor,
    onClick: () => {
      if (open) close();
      else setOpen(true);
    },
    onKeyDown: (event) => {
      if (role === "menu" && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
        event.preventDefault();
        if (open) panel?.querySelector<HTMLElement>("[role=menuitem]:not([disabled])")?.focus();
        else {
          setFocusFirst(true);
          setOpen(true);
        }
      }
    },
    "aria-haspopup": role,
    "aria-expanded": open,
    "aria-controls": id,
  };

  const origin = position ? `${position.placement.startsWith("bottom") ? "top" : "bottom"} ${(position.placement.endsWith("start") ? !position.rtl : position.rtl) ? "left" : "right"}` : undefined;

  return (
    <>
      {trigger(triggerProps)}
      <div
        ref={setPanel}
        id={id}
        popover="manual"
        role={role}
        aria-label={label}
        data-state={shown ? "open" : "closed"}
        onKeyDown={onKeyDown}
        style={{ left: position?.left ?? 0, top: position?.top ?? 0, transformOrigin: origin }}
        className={cx("floating-panel", className)}
      >
        {open || position ? (typeof children === "function" ? children({ close }) : children) : null}
      </div>
    </>
  );
}
