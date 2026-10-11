import { isDay } from "@business-os/i18n/dates";

export type TimeOffProblem = "invalid_date" | "ends_before_start" | "in_the_past" | "too_long";

/** Checks a time-off request before it is sent; the API repeats the same rules. */
export function timeOffProblem(startsOn: string, endsOn: string, today: string): TimeOffProblem | null {
  if (!isDay(startsOn) || !isDay(endsOn)) return "invalid_date";
  if (endsOn < startsOn) return "ends_before_start";
  if (endsOn < today) return "in_the_past";
  if ((Date.parse(endsOn) - Date.parse(startsOn)) / 86_400_000 > 366) return "too_long";
  return null;
}
