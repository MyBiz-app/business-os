/** Pure helpers behind the client app's home, bookings and updates screens. */

/** The home cards the app knows how to draw (CLIENT_HOME_CARDS in packages/verticals). */
export const KNOWN_HOME_CARDS = [
  "next_booking", "membership", "shortcuts", "rebook", "dependents", "health",
  "documents", "quotes", "addresses", "updates", "business_info",
] as const;
export type HomeCard = (typeof KNOWN_HOME_CARDS)[number];

/** The cards to draw: the API's list, in its order, without ones this app version doesn't
 * know yet (a newer API can list a card an older app can't draw), and without repeats. */
export function knownCards(listed: readonly string[] | null | undefined): HomeCard[] {
  const known = new Set<string>(KNOWN_HOME_CARDS);
  const seen = new Set<string>();
  const cards: HomeCard[] = [];
  for (const card of listed ?? []) {
    if (!known.has(card) || seen.has(card)) continue;
    seen.add(card);
    cards.push(card as HomeCard);
  }
  return cards;
}

const stamp = (instant: string): string => instant.replace(/[-:]/g, "").replace(/\.\d+/, "").replace(/\+00:00$/, "Z");

/** A link that adds a booking to the phone's calendar (opens the calendar's own "new event"
 * page, so it needs no calendar permission and works on the web too). */
export function calendarLink(event: { title: string; startsAt: string; endsAt: string; location?: string | null; details?: string }): string {
  const q = new URLSearchParams({
    action: "TEMPLATE",
    text: event.title,
    dates: `${stamp(new Date(event.startsAt).toISOString())}/${stamp(new Date(event.endsAt).toISOString())}`,
  });
  if (event.location) q.set("location", event.location);
  if (event.details) q.set("details", event.details);
  return `https://calendar.google.com/calendar/render?${q.toString()}`;
}

type Booking = { starts_at: string; status: string; session_status: string };

/** Whether a booking is still ahead and can be cancelled or navigated to. */
export function isUpcoming(booking: Booking, now: number): boolean {
  return Date.parse(booking.starts_at) >= now && booking.session_status !== "cancelled" && (booking.status === "booked" || booking.status === "waitlisted");
}

/** The soonest upcoming booking that holds a place (not a waitlist spot). */
export function nextBooking<T extends Booking>(bookings: readonly T[], now: number): T | undefined {
  return bookings
    .filter((b) => isUpcoming(b, now) && b.status === "booked")
    .sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at))[0];
}

/** The latest visit that took place (not cancelled), to offer "book again". */
export function lastVisit<T extends Booking>(bookings: readonly T[], now: number): T | undefined {
  return bookings
    .filter((b) => Date.parse(b.starts_at) < now && b.session_status !== "cancelled" && (b.status === "checked_in" || b.status === "booked"))
    .sort((a, b) => Date.parse(b.starts_at) - Date.parse(a.starts_at))[0];
}

/** Whether cancelling now counts as late under the business's window. */
export function isLateCancel(startsAt: string, windowMinutes: number, now: number): boolean {
  return Date.parse(startsAt) - now < windowMinutes * 60_000;
}

/** Splits dated items into "today", "this week" and "earlier" for the updates list; `day` turns
 * an instant into the business's local calendar day (YYYY-MM-DD). */
export function groupByRecency<T>(
  items: readonly T[],
  when: (item: T) => string,
  day: (instant: string) => string,
  today: string,
  weekAgo: string,
): { key: "today" | "week" | "earlier"; items: T[] }[] {
  const groups: Record<"today" | "week" | "earlier", T[]> = { today: [], week: [], earlier: [] };
  for (const item of items) {
    const d = day(when(item));
    groups[d >= today ? "today" : d > weekAgo ? "week" : "earlier"].push(item);
  }
  return (["today", "week", "earlier"] as const).filter((key) => groups[key].length > 0).map((key) => ({ key, items: groups[key] }));
}
