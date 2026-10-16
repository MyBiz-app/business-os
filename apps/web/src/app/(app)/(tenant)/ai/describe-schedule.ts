import type { useTranslations } from "next-intl";

type Translate = ReturnType<typeof useTranslations<"aiTeam">>;

/** A task's schedule as the API keeps it: local time in the business's time zone. */
export type Schedule = { type: string; time?: string; date?: string; weekdays?: number[]; day?: number };

/** Weekday names, Monday = 0 like the API (2024-01-01 was a Monday). */
export function weekdayNames(locale: string): string[] {
  const format = new Intl.DateTimeFormat(locale, { weekday: "long", timeZone: "UTC" });
  return Array.from({ length: 7 }, (_, i) => format.format(new Date(Date.UTC(2024, 0, 1 + i))));
}

/** "Every Sunday at 08:00", "Every day at 08:00", "18 Oct 2026 at 07:00"... in the reader's language. */
export function describeSchedule(schedule: Schedule, t: Translate, locale: string): string {
  const time = schedule.time ?? "";
  switch (schedule.type) {
    case "once": {
      const date = schedule.date ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${schedule.date}T12:00:00Z`)) : "";
      return t("tasks.when.once", { date, time });
    }
    case "weekly": {
      const names = weekdayNames(locale);
      const days = new Intl.ListFormat(locale, { style: "long", type: "conjunction" }).format((schedule.weekdays ?? []).map((d) => names[d] ?? ""));
      return t("tasks.when.weekly", { days, time });
    }
    case "monthly":
      return t("tasks.when.monthly", { day: schedule.day ?? 1, time });
    default:
      return t("tasks.when.daily", { time });
  }
}
