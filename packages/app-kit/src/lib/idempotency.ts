/** A fresh key for one action (a sale, a payment): sending the same key again never repeats it,
 * so a retry after a dropped connection is safe. Make a new one after the action succeeds. */
export function newIdempotencyKey(now: number = Date.now()): string {
  const random = Array.from({ length: 3 }, () => Math.random().toString(36).slice(2, 8)).join("");
  return `app-${now.toString(36)}-${random}`;
}
