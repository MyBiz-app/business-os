import type { components } from "@business-os/api-client";
import { getTranslations } from "next-intl/server";

import { ScrollRegion } from "@/components/scroll-region";
import { addDays, formatDay } from "@/lib/dates";

type Row = components["schemas"]["BreakdownItem"];

// A Monday, to name ISO weekdays (1 = Monday) in the user's language.
const MONDAY = "2024-01-01";

/** When people come: a day × hour grid shaded by check-ins. It is a real table, so screen
 * readers get each count; the shading is a visual summary on top. */
export async function BusyHours({ rows, locale }: { rows: Row[]; locale: string }) {
  const t = await getTranslations("reports");
  const attended = new Map(rows.map((row) => [row.key, row.attended]));
  const hours = rows.map((row) => Number(row.key.split("-")[1]));
  const first = Math.min(...hours);
  const last = Math.max(...hours);
  const columns = Array.from({ length: last - first + 1 }, (_, i) => first + i);
  // The week starts on Sunday where the calendar does (Hebrew), on Monday elsewhere.
  const weekdays = locale.startsWith("he") ? [7, 1, 2, 3, 4, 5, 6] : [1, 2, 3, 4, 5, 6, 7];
  const max = Math.max(1, ...rows.map((row) => row.attended));
  const dayName = (weekday: number, style: "short" | "long") =>
    formatDay(addDays(MONDAY, weekday - 1), locale, { weekday: style });
  const hourLabel = (hour: number) => `${String(hour).padStart(2, "0")}:00`;
  const busiest = [...rows].sort((a, b) => b.attended - a.attended)[0];
  const [busyDay, busyHour] = busiest.key.split("-").map(Number);

  return (
    <section aria-labelledby="busy-heading" className="flex flex-col gap-4 card p-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div className="flex flex-col gap-1">
          <h2 id="busy-heading" className="text-lg font-semibold">
            {t("bySlot")}
          </h2>
          <p className="text-sm text-muted">{t("heatmap.hint")}</p>
        </div>
        <p className="text-sm font-medium">{t("heatmap.busiest", { slot: `${dayName(busyDay, "long")} ${hourLabel(busyHour)}` })}</p>
      </div>
      <ScrollRegion labelledBy="busy-heading">
        <table className="w-full border-separate border-spacing-1 text-xs">
          <thead>
            <tr>
              <td />
              {columns.map((hour) => (
                <th key={hour} scope="col" className="min-w-8 font-normal text-muted tabular-nums">
                  {String(hour).padStart(2, "0")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weekdays.map((weekday) => (
              <tr key={weekday}>
                <th scope="row" className="whitespace-nowrap pe-2 text-start font-medium text-muted">
                  {dayName(weekday, "short")}
                </th>
                {columns.map((hour) => {
                  const count = attended.get(`${weekday}-${hour}`) ?? 0;
                  const label = t("heatmap.cell", { day: dayName(weekday, "long"), hour: hourLabel(hour), count });
                  return (
                    <td
                      key={hour}
                      title={label}
                      className="h-8 rounded-md bg-foreground/4"
                      style={count ? { background: `color-mix(in oklab, var(--primary) ${Math.round(12 + (count / max) * 88)}%, transparent)` } : undefined}
                    >
                      <span className="sr-only">{label}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
      <div aria-hidden="true" className="flex items-center justify-end gap-1.5 text-xs text-muted">
        {t("heatmap.less")}
        {[12, 34, 56, 78, 100].map((level) => (
          <span key={level} className="size-3.5 rounded" style={{ background: `color-mix(in oklab, var(--primary) ${level}%, transparent)` }} />
        ))}
        {t("heatmap.more")}
      </div>
    </section>
  );
}
