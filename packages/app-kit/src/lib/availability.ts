/** One stretch of a weekday a person can work shifts (0 = Monday, times as "HH:MM"). */
export type AvailabilityDraft = { weekday: number; starts: string; ends: string };

export type AvailabilityProblem = "invalid_time" | "ends_before_start" | "overlap";

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;

/** "8:00" or "08:00:00" as "08:00"; anything else unchanged (and then refused). */
export function normalizeTime(value: string): string {
  const match = /^(\d{1,2}):(\d{2})(?::\d{2})?$/.exec(value.trim());
  return match ? `${match[1].padStart(2, "0")}:${match[2]}` : value.trim();
}

/** Checks a week before it is saved; the API repeats the same rules. "24:00" is not a time:
 * the end of the day is "23:59". */
export function availabilityProblem(windows: AvailabilityDraft[]): AvailabilityProblem | null {
  const clean = windows.map((w) => ({ ...w, starts: normalizeTime(w.starts), ends: normalizeTime(w.ends) }));
  if (clean.some((w) => !TIME.test(w.starts) || !TIME.test(w.ends))) return "invalid_time";
  if (clean.some((w) => w.ends <= w.starts)) return "ends_before_start";
  const sorted = [...clean].sort((a, b) => a.weekday - b.weekday || a.starts.localeCompare(b.starts));
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].weekday === sorted[i - 1].weekday && sorted[i].starts < sorted[i - 1].ends) return "overlap";
  }
  return null;
}

/** The order the days are shown in: Sunday first where the week starts on Sunday (Israel, US). */
export function weekdayOrder(sundayFirst: boolean): number[] {
  return sundayFirst ? [6, 0, 1, 2, 3, 4, 5] : [0, 1, 2, 3, 4, 5, 6];
}
