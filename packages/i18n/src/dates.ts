/** Calendar dates as "YYYY-MM-DD" strings, computed without the server's own time zone. */

export function todayIn(timeZone: string, now: Date = new Date()): string {
  // en-CA formats as YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

export function addDays(day: string, days: number): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** 0 = Sunday … 6 = Saturday. */
export function weekdayOf(day: string): number {
  return new Date(`${day}T00:00:00Z`).getUTCDay();
}

/** The Sunday that starts the week containing `day` (weeks start on Sunday in Israel and the US). */
export function weekStart(day: string): string {
  return addDays(day, -weekdayOf(day));
}

export function isDay(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value));
}

/** The local date (in `timeZone`) of an instant. */
export function dayOf(instant: string, timeZone: string): string {
  return todayIn(timeZone, new Date(instant));
}

/** API weekdays are 0 = Monday … 6 = Sunday; JavaScript's are 0 = Sunday. */
export function toApiWeekday(jsWeekday: number): number {
  return (jsWeekday + 6) % 7;
}

export function formatTime(instant: string, locale: string, timeZone: string): string {
  return new Intl.DateTimeFormat(locale, { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(
    new Date(instant),
  );
}

/** Formats a calendar day (no time zone shift: the day is the day). */
export function formatDay(day: string, locale: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(locale, { ...options, timeZone: "UTC" }).format(new Date(`${day}T12:00:00Z`));
}
