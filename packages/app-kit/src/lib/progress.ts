import { addDays, dayOf, weekStart } from "@business-os/i18n/dates";

type Visit = { starts_at: string; status: string; session_status: string };

export type Progress = {
  /** Visits in the current calendar week (weeks start on Sunday). */
  weekVisits: number;
  /** Visits in the current calendar month. */
  monthVisits: number;
  /** Weeks in a row with at least one visit, counting back from this week (or last, when this week has none yet). */
  streakWeeks: number;
  total: number;
};

/** A visit that took place: attended, or booked and over without being marked a no-show or cancelled. */
function tookPlace(visit: Visit, now: number): boolean {
  if (visit.session_status === "cancelled") return false;
  return visit.status === "checked_in" || (visit.status === "booked" && Date.parse(visit.starts_at) < now);
}

/** The client's rhythm in one business, from their booking history; days are in the business's time zone. */
export function progressOf(bookings: readonly Visit[], timeZone: string, now: number = Date.now()): Progress {
  const today = dayOf(new Date(now).toISOString(), timeZone);
  const days = bookings.filter((b) => tookPlace(b, now)).map((b) => dayOf(b.starts_at, timeZone));
  const thisWeek = weekStart(today);
  const weeks = new Set(days.map(weekStart));
  let cursor = weeks.has(thisWeek) ? thisWeek : addDays(thisWeek, -7);
  let streakWeeks = 0;
  while (weeks.has(cursor)) {
    streakWeeks += 1;
    cursor = addDays(cursor, -7);
  }
  return {
    weekVisits: days.filter((d) => weekStart(d) === thisWeek).length,
    monthVisits: days.filter((d) => d.slice(0, 7) === today.slice(0, 7)).length,
    streakWeeks,
    total: days.length,
  };
}
