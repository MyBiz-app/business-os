// Pure logic of the "all mine" view of the client app: one person, several businesses.

export type Waiting = { business_id: string; kind: string };

/** The business a sideways swipe moves to: the next or previous one in the strip, never wrapping
 * around. `step` is +1 for the next one, -1 for the previous one. */
export function neighbour(ids: string[], currentId: string | null, step: 1 | -1): string | null {
  const index = currentId ? ids.indexOf(currentId) : -1;
  if (index < 0) return null;
  return ids[index + step] ?? null;
}

/** Which way a finished drag swipes: a clear sideways move (not a scroll), long enough to mean it.
 * Dragging toward the start of the line (left in LTR, right in RTL) goes to the next business. */
export function swipeStep(dx: number, dy: number, rtl: boolean): 1 | -1 | null {
  if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 2) return null;
  const towardStart = rtl ? dx > 0 : dx < 0;
  return towardStart ? 1 : -1;
}

/** How many things wait for the person in each business: the dot on its circle. */
export function waitingCounts(waiting: Waiting[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const item of waiting) counts[item.business_id] = (counts[item.business_id] ?? 0) + 1;
  return counts;
}

/** The initials shown in a business's circle when it has no logo (first letters of two words). */
export function circleInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const letters = words.length > 1 ? [words[0], words[1]] : [words[0]];
  return letters.map((word) => Array.from(word ?? "")[0] ?? "").join("").toUpperCase();
}

/** Where "book again" opens, by how the thing was booked. */
export function rebookTarget(mode: string): "/schedule" | "/appointment" | "/court" {
  return mode === "appointment" ? "/appointment" : mode === "resource" ? "/court" : "/schedule";
}
