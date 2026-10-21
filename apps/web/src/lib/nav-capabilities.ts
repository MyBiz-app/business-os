/** The side menu shows capabilities the business hasn't enabled in soft grey, so they are
 * discoverable. After this many days from the business's creation they fold into one
 * "Add capabilities" item, so the menu stays about what the business uses. */
export const LOCKED_GRACE_DAYS = 30;

const DAY_MS = 24 * 60 * 60 * 1000;

/** `items`: each missing capability has its own grey item. `folded`: one "Add capabilities" item. */
export function lockedMenuMode(createdAt: string | null | undefined, now: number = Date.now()): "items" | "folded" {
  if (!createdAt) return "items";
  const created = Date.parse(createdAt);
  if (Number.isNaN(created)) return "items";
  return now - created >= LOCKED_GRACE_DAYS * DAY_MS ? "folded" : "items";
}
