/** Maths of the two-handle range slider, kept apart from the view so it can be tested. */

export type Range = { from: number; to: number };

/** The nearest step inside [min, max] for a position along the track (0 is the start, 1 the end). */
export function valueAt(fraction: number, min: number, max: number, step: number): number {
  const clamped = Math.min(1, Math.max(0, fraction));
  const snapped = Math.round((min + clamped * (max - min)) / step) * step;
  return Math.min(max, Math.max(min, snapped));
}

/** Where a value sits along the track, from 0 to 1. */
export function fractionOf(value: number, min: number, max: number): number {
  return max === min ? 0 : (Math.min(max, Math.max(min, value)) - min) / (max - min);
}

/** Moves one handle and keeps at least `gap` between the two (the other handle never moves). */
export function moveHandle(range: Range, handle: "from" | "to", value: number, min: number, max: number, gap: number): Range {
  if (handle === "from") return { from: Math.min(Math.max(min, value), range.to - gap), to: range.to };
  return { from: range.from, to: Math.max(Math.min(max, value), range.from + gap) };
}
