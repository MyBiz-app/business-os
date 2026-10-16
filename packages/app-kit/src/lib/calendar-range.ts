import { addDays, addMonths, monthGrid, weekStart } from "@business-os/i18n/dates";

export type CalendarView = "day" | "week" | "month";

/** The most days one schedule request may cover (the API limit). */
export const MAX_REQUEST_DAYS = 14;

/** The days a view needs data for. Day view prefetches the days next to it so the strip feels instant. */
export function rangeFor(view: CalendarView, day: string): { start: string; days: number } {
  if (view === "week") return { start: weekStart(day), days: 7 };
  if (view === "month") return monthGrid(day);
  return { start: addDays(day, -3), days: 7 };
}

/** Splits a range into requests the API accepts. */
export function chunkRange(start: string, days: number, size: number = MAX_REQUEST_DAYS): { start: string; days: number }[] {
  const parts: { start: string; days: number }[] = [];
  for (let offset = 0; offset < days; offset += size) {
    parts.push({ start: addDays(start, offset), days: Math.min(size, days - offset) });
  }
  return parts;
}

/** The day to show after moving one step (a day, a week or a month) in a direction. */
export function stepDay(view: CalendarView, day: string, direction: 1 | -1): string {
  if (view === "month") return addMonths(day, direction);
  return addDays(day, direction * (view === "week" ? 7 : 1));
}

/** One level up (day → week → month) or down; stays put at the ends. */
export function shiftView(view: CalendarView, direction: "up" | "down"): CalendarView {
  const order: CalendarView[] = ["day", "week", "month"];
  const next = order.indexOf(view) + (direction === "up" ? 1 : -1);
  return order[Math.min(order.length - 1, Math.max(0, next))];
}
