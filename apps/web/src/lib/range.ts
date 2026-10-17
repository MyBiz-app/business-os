import { addDays, isDay, monthStart } from "./dates";

/** The longest custom range, in days; the API refuses more (reports 366, sales 367). */
export const MAX_RANGE_DAYS = 366;

export type RangeKey = `${number}` | "custom";

export type DateRange = {
  /** The chosen preset ("30"), or "custom" when `from` and `to` came from the link. */
  key: RangeKey;
  start: string;
  end: string;
  days: number;
};

const spanOf = (start: string, end: string) => Math.round((Date.parse(end) - Date.parse(start)) / 86_400_000) + 1;

/** The range a page shows, from its link: `?period=30` for a preset or `?from=...&to=...` for a
 * free range. Presets end yesterday (completed days only, so the comparison with the previous
 * period is fair) unless `includeToday` is set. A bad or too long free range falls back to the
 * default preset. */
export function resolveRange(
  query: Record<string, string | string[] | undefined>,
  today: string,
  { presets, fallback, includeToday = false }: { presets: readonly number[]; fallback: number; includeToday?: boolean },
): DateRange {
  const { from, to } = query;
  if (isDay(from) && isDay(to) && from <= to && to <= today && spanOf(from, to) <= MAX_RANGE_DAYS) {
    return { key: "custom", start: from, end: to, days: spanOf(from, to) };
  }
  const chosen = presets.find((days) => String(days) === query.period) ?? fallback;
  const end = includeToday ? today : addDays(today, -1);
  return { key: String(chosen) as RangeKey, start: addDays(end, -(chosen - 1)), end, days: chosen };
}

/** The quick picks next to the date fields of a free range. */
export function rangeShortcuts(today: string): { key: "thisMonth" | "lastMonth" | "yearToDate"; from: string; to: string }[] {
  const thisMonth = monthStart(today);
  const lastMonthEnd = addDays(thisMonth, -1);
  return [
    { key: "thisMonth", from: thisMonth, to: today },
    { key: "lastMonth", from: monthStart(lastMonthEnd), to: lastMonthEnd },
    { key: "yearToDate", from: `${today.slice(0, 4)}-01-01`, to: today },
  ];
}
