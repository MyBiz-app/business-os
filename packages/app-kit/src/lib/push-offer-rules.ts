/** When to offer "turn on reminders": once, right after a booking, never to someone who already
 * decided. The phone itself only shows its own permission prompt once, so the offer is the one
 * chance to explain why before it is spent. */

export type PushPermission = "granted" | "denied" | "undetermined";

/** How long a "Not now" is respected. */
export const OFFER_PAUSE_DAYS = 14;

export function shouldOfferPush({
  available,
  permission,
  lastAnswerAt,
  now = Date.now(),
}: {
  /** Native with a push project id: nothing to offer on the web. */
  available: boolean;
  permission: PushPermission;
  /** When the person last said "Not now" (a time in ms), if ever. */
  lastAnswerAt: number | null;
  now?: number;
}): boolean {
  if (!available || permission !== "undetermined") return false;
  if (lastAnswerAt === null) return true;
  return now - lastAnswerAt >= OFFER_PAUSE_DAYS * 24 * 60 * 60 * 1000;
}
