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

/** Formats a calendar day (no time zone shift: the day is the day). An instant ("2026-09-01T18:34:00Z")
 * is accepted too and shows its UTC day: callers pass API timestamps straight in, and a time after the
 * day made the date invalid and crashed the page. Use `dayOf` first when the business's day matters. */
export function formatDay(day: string, locale: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(locale, { ...options, timeZone: "UTC" }).format(new Date(`${day.slice(0, 10)}T12:00:00Z`));
}

/** The first day of the month of `day`. */
export function monthStart(day: string): string {
  return `${day.slice(0, 7)}-01`;
}

/** The same day-of-month in another month, or that month's last day when it is shorter. */
export function addMonths(day: string, months: number): string {
  const [year, month, date] = day.split("-").map(Number);
  const target = new Date(Date.UTC(year, month - 1 + months, 1));
  const last = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  target.setUTCDate(Math.min(date, last));
  return target.toISOString().slice(0, 10);
}

/** The weeks that show the month of `day`: the Sunday before its first day and the number of days
 * (a whole number of weeks, at most 42). */
export function monthGrid(day: string): { start: string; days: number } {
  const first = monthStart(day);
  const [year, month] = first.split("-").map(Number);
  const length = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const offset = weekdayOf(first);
  return { start: weekStart(first), days: Math.ceil((offset + length) / 7) * 7 };
}

/** The wall-clock reading of an instant in a time zone, as "YYYY-MM-DDTHH:mm" (what a
 * `datetime-local` input holds). */
export function localValue(instant: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(instant));
  const part = (type: string) => parts.find((p) => p.type === type)?.value ?? "00";
  return `${part("year")}-${part("month")}-${part("day")}T${part("hour")}:${part("minute")}`;
}

/** The instant (ISO, UTC) at which a time zone's clock reads `local` ("YYYY-MM-DDTHH:mm"). */
export function localToInstant(local: string, timeZone: string): string {
  const wanted = Date.parse(`${local}:00Z`);
  let guess = wanted;
  // The zone's offset depends on the instant; two passes settle it across a clock change.
  for (let pass = 0; pass < 2; pass++) {
    guess = wanted - (Date.parse(`${localValue(new Date(guess).toISOString(), timeZone)}:00Z`) - guess);
  }
  return new Date(guess).toISOString();
}
