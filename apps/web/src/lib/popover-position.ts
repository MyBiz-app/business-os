/** Where a floating panel (a menu, a popover) goes relative to the element that opened it. The one
 * positioning method of the product: the panel is fixed to the viewport at the returned point, so
 * no parent's overflow or stacking can clip or hide it. */

export type Side = "bottom" | "top";
/** start / end follow the reading direction: the left edge in English, the right edge in Hebrew. */
export type Align = "start" | "end";
export type Placement = `${Side}-${Align}`;

export type Box = { left: number; top: number; width: number; height: number };

export type PopoverPosition = { left: number; top: number; placement: Placement };

/** `anchor` and `viewport` are in viewport coordinates (getBoundingClientRect). The panel opens on
 * the preferred side, flips to the other when it does not fit there but does fit on the other, and
 * is kept `margin` pixels inside the viewport sideways. */
export function computePopoverPosition({
  anchor,
  panel,
  viewport,
  placement = "bottom-start",
  rtl = false,
  gap = 8,
  margin = 8,
}: {
  anchor: Box;
  panel: { width: number; height: number };
  viewport: { width: number; height: number };
  placement?: Placement;
  rtl?: boolean;
  gap?: number;
  margin?: number;
}): PopoverPosition {
  const [preferredSide, align] = placement.split("-") as [Side, Align];

  const below = anchor.top + anchor.height + gap;
  const above = anchor.top - gap - panel.height;
  const fitsBelow = below + panel.height <= viewport.height - margin;
  const fitsAbove = above >= margin;
  const side: Side = preferredSide === "bottom" ? (fitsBelow || !fitsAbove ? "bottom" : "top") : fitsAbove || !fitsBelow ? "top" : "bottom";
  const top = side === "bottom" ? below : above;

  // The panel's edge on the "start" side lines up with the anchor's: left in LTR, right in RTL.
  const alignLeft = (align === "start") !== rtl;
  const raw = alignLeft ? anchor.left : anchor.left + anchor.width - panel.width;
  const maxLeft = Math.max(margin, viewport.width - margin - panel.width);
  const left = Math.min(Math.max(raw, margin), maxLeft);

  return { left, top: Math.max(top, margin), placement: `${side}-${align}` };
}
