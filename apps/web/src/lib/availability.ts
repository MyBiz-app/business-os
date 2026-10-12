/** The hours of a weekday a person said they can work shifts (0 = Monday, times as "HH:MM"). */
export type AvailabilityWindow = { weekday: number; starts: string; ends: string };

/** Monday-first weekday of a "YYYY-MM-DD" day. */
export function mondayWeekday(day: string): number {
  return (new Date(`${day}T12:00:00Z`).getUTCDay() + 6) % 7;
}

/** Whether a shift on `day` from `starts` to `ends` ("HH:MM"; an end at or before the start is
 * the next day) falls outside what the person said. Mirrors `app.outside_availability` in the
 * API: not said (null or empty) is never outside; past midnight needs the evening up to 23:59
 * and, the next day, a stretch from 00:00. */
export function outsideAvailability(windows: AvailabilityWindow[] | null | undefined, day: string, starts: string, ends: string): boolean {
  if (!windows?.length) return false;
  const weekday = mondayWeekday(day);
  const short = (time: string) => time.slice(0, 5);
  const sameDay = ends > starts;
  return !windows.some((w) => {
    if (w.weekday !== weekday || short(w.starts) > starts) return false;
    if (sameDay) return short(w.ends) >= ends;
    if (short(w.ends) < "23:59") return false;
    if (ends === "00:00") return true;
    const next = (weekday + 1) % 7;
    return windows.some((n) => n.weekday === next && short(n.starts) === "00:00" && short(n.ends) >= ends);
  });
}
