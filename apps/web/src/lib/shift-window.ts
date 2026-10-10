import { addDays, weekStart } from "./dates";

export type Cadence = "daily" | "weekly" | "monthly" | "custom";
export type Range = "day" | "week" | "month" | "custom";

export const RANGES: Range[] = ["day", "week", "month", "custom"];

/** The board window a branch's planning rhythm opens on. */
export function rangeOfCadence(cadence: Cadence | undefined): Range {
  return cadence === "daily" ? "day" : cadence === "monthly" ? "month" : cadence === "custom" ? "custom" : "week";
}

export function isRange(value: unknown): value is Range {
  return typeof value === "string" && (RANGES as string[]).includes(value);
}

function daysInMonth(day: string): number {
  const [year, month] = day.split("-").map(Number);
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

export type ShiftWindow = { start: string; days: number };

/** The days shown for `range` around `date`: a day, the Sunday-to-Saturday week, the calendar
 * month, or `customDays` days starting at `date`. */
export function windowOf(range: Range, date: string, customDays = 14): ShiftWindow {
  if (range === "day") return { start: date, days: 1 };
  if (range === "week") return { start: weekStart(date), days: 7 };
  if (range === "month") {
    const start = `${date.slice(0, 7)}-01`;
    return { start, days: daysInMonth(start) };
  }
  return { start: date, days: customDays };
}

/** The anchor date of the previous (-1) or next (1) window. */
export function stepWindow(range: Range, window: ShiftWindow, direction: 1 | -1): string {
  if (range === "month") {
    const [year, month] = window.start.split("-").map(Number);
    const target = new Date(Date.UTC(year, month - 1 + direction, 1));
    return target.toISOString().slice(0, 10);
  }
  return addDays(window.start, direction * window.days);
}

/** How many branches can be shown side by side before the board gets hard to read. */
export function branchLimit(range: Range): number {
  return range === "day" ? 12 : range === "week" ? 3 : range === "month" ? 1 : 2;
}
