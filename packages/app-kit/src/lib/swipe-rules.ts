/** How far a row has to be dragged (in px) before letting go counts as choosing the action. */
export const SWIPE_COMMIT = 72;

/** The widest a row can be pulled open, as a multiple of the commit distance. */
const MAX_PULL = 1.4;

/** A row is dragged toward the side its action is on: toward the right in left-to-right layouts,
 * toward the left in right-to-left ones. Returns the drag distance along that direction (never
 * negative), clamped to how far the row may open. */
export function pullDistance(dx: number, rtl: boolean): number {
  const along = rtl ? -dx : dx;
  return Math.min(Math.max(along, 0), SWIPE_COMMIT * MAX_PULL);
}

/** Whether a gesture is a deliberate sideways swipe (not a scroll): it has moved enough, mostly sideways. */
export function isSideways(dx: number, dy: number): boolean {
  return Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy) * 1.5;
}

/** Whether letting go at this distance runs the action. */
export function commits(distance: number): boolean {
  return distance >= SWIPE_COMMIT;
}
