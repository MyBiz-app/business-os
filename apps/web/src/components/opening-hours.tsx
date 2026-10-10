import { getTranslations } from "next-intl/server";

/** A branch's week of opening hours, read-only (0 = Monday; a day with nothing is closed). */
export async function OpeningHoursList({ hours, weekStartsOn }: { hours: { weekday: number; opens: string; closes: string }[]; weekStartsOn: number }) {
  const t = await getTranslations("hours");
  const tOpening = await getTranslations("openingHours");
  const names = t.raw("weekdays") as string[];
  const days = Array.from({ length: 7 }, (_, i) => (weekStartsOn + i) % 7);
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-sm">
      {days.map((day) => {
        const intervals = hours.filter((h) => h.weekday === day);
        return (
          <div key={day} className="contents">
            <dt className="font-medium">{names[day]}</dt>
            <dd className={intervals.length ? "tabular-nums" : "text-muted"} dir={intervals.length ? "ltr" : undefined}>
              {intervals.length ? intervals.map((h) => `${h.opens.slice(0, 5)}–${h.closes.slice(0, 5)}`).join(", ") : tOpening("closed")}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
