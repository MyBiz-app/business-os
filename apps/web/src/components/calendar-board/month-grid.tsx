import Link from "next/link";

import { addDays, formatDay } from "@/lib/dates";

import type { GridEvent } from "./time-grid";

type Props = {
  /** The Sunday the first row starts on. */
  start: string;
  /** A whole number of weeks. */
  days: number;
  /** The month shown, `YYYY-MM`; days around it are dimmed. */
  month: string;
  today: string;
  locale: string;
  events: GridEvent[];
  closed: Record<string, string | null>;
  labels: { closed: string; more: string; empty: string };
  /** The day view's address with `__day__` for the day. */
  dayHref: string;
};

const CHIPS = 3;

/** A month as weeks of day cells: each lists its first sessions and links to the day for the rest. */
export function MonthGrid({ start, days, month, today, locale, events, closed, labels, dayHref }: Props) {
  const all = Array.from({ length: days }, (_, i) => addDays(start, i));
  const byDay = new Map<string, GridEvent[]>();
  for (const event of [...events].sort((a, b) => a.start - b.start)) byDay.set(event.day, [...(byDay.get(event.day) ?? []), event]);

  return (
    <div className="card overflow-hidden p-0">
      <div className="grid grid-cols-7 border-b border-border bg-surface text-center text-xs font-semibold text-muted">
        {all.slice(0, 7).map((day) => (
          <div key={day} className="py-2">
            {formatDay(day, locale, { weekday: "short" })}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {all.map((day) => {
          const own = byDay.get(day) ?? [];
          const inMonth = day.startsWith(month);
          const isToday = day === today;
          return (
            <div
              key={day}
              className={`flex min-h-24 flex-col gap-1 border-b border-s border-border p-1.5 sm:min-h-32 ${inMonth ? "" : "bg-foreground/[0.03] text-muted"} ${closed[day] !== undefined ? "bg-[repeating-linear-gradient(135deg,transparent_0_8px,color-mix(in_oklab,var(--foreground)_5%,transparent)_8px_16px)]" : ""}`}
            >
              <div className="flex items-center justify-between gap-1">
                <Link
                  href={dayHref.replace("__day__", day)}
                  aria-current={isToday ? "date" : undefined}
                  className={`flex size-7 items-center justify-center rounded-full text-sm font-semibold tabular-nums transition-colors ${isToday ? "bg-primary text-on-primary" : "hover:bg-foreground/8"}`}
                >
                  {formatDay(day, locale, { day: "numeric" })}
                </Link>
                {closed[day] !== undefined && (
                  <span className="truncate rounded-full bg-warning/15 px-1.5 text-[0.6875rem] font-semibold text-foreground" title={closed[day] ?? undefined}>
                    {labels.closed}
                  </span>
                )}
              </div>
              <ul className="flex flex-col gap-0.5">
                {own.slice(0, CHIPS).map((event) => (
                  <li key={event.id}>
                    <Link
                      href={event.href}
                      title={`${event.time} · ${event.title}`}
                      className={`flex items-center gap-1 overflow-hidden rounded-md border-s-[3px] px-1 py-0.5 text-[0.6875rem] leading-tight hover:shadow-sm ${event.cancelled ? "line-through opacity-55" : ""}`}
                      style={{ borderInlineStartColor: event.color, background: `color-mix(in oklab, ${event.color} 14%, var(--surface))` }}
                    >
                      <span className="hidden shrink-0 font-semibold tabular-nums sm:inline" dir="ltr">
                        {event.time.split("–")[0]}
                      </span>
                      <span className="truncate" dir="auto">
                        {event.title}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
              {own.length > CHIPS && (
                <Link href={dayHref.replace("__day__", day)} className="px-1 text-[0.6875rem] font-semibold text-muted hover:text-primary">
                  {labels.more.replace("{count}", String(own.length - CHIPS))}
                </Link>
              )}
            </div>
          );
        })}
      </div>
      {events.length === 0 && <p className="border-t border-border p-4 text-center text-sm text-muted">{labels.empty}</p>}
    </div>
  );
}
