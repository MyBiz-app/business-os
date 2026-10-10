"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { Avatar } from "@/components/avatar";
import { layOut, minutesIn, visibleHours } from "@/lib/calendar";
import { formatDay, todayIn } from "@/lib/dates";

export type GridEvent = {
  id: string;
  href: string;
  day: string;
  start: number;
  end: number;
  time: string;
  title: string;
  detail: string | null;
  color: string;
  /** Shown when several branches share the grid. */
  branch: { name: string; color: string } | null;
  cancelled: boolean;
};

export type GridShift = { id: string; day: string; start: number; end: number; userId: string; name: string; avatar: string | null; label: string; warn: boolean };

type Props = {
  days: string[];
  timeZone: string;
  locale: string;
  events: GridEvent[];
  shifts: GridShift[];
  closed: Record<string, string | null>;
  /** Opening intervals per day (minutes), when one branch is shown; none: not shaded. */
  open: Record<string, { start: number; end: number }[]> | null;
  labels: { now: string; closed: string; shifts: string; empty: string };
};

const HOUR = 64; // pixels per hour

/** The day or week as a time grid: events where they happen, overlapping ones side by side,
 * shifts in a narrow lane, closed hours shaded and a live line at the current time. */
export function TimeGrid({ days, timeZone, locale, events, shifts, closed, open, labels }: Props) {
  const range = useMemo(
    () => visibleHours([...events, ...shifts, ...Object.values(open ?? {}).flat()].filter((e) => e.end > e.start)),
    [events, shifts, open],
  );
  const height = ((range.to - range.from) / 60) * HOUR;
  const y = (minutes: number) => ((minutes - range.from) / 60) * HOUR;
  const hours = Array.from({ length: (range.to - range.from) / 60 }, (_, i) => range.from / 60 + i);

  // The current time, refreshed every 30 seconds (the server's "now" may be stale by then).
  const [now, setNow] = useState<{ day: string; minutes: number } | null>(null);
  useEffect(() => {
    const tick = () => setNow({ day: todayIn(timeZone), minutes: minutesIn(new Date(), timeZone) });
    tick();
    const timer = window.setInterval(tick, 30_000);
    return () => window.clearInterval(timer);
  }, [timeZone]);

  // Opens at the current hour (or the first event), without moving the page itself.
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = scroller.current;
    if (!element) return;
    const today = todayIn(timeZone);
    const target = days.includes(today)
      ? minutesIn(new Date(), timeZone) - 90
      : Math.min(...events.map((e) => e.start), range.to) - 30;
    element.scrollTop = Math.max(0, y(target));
    // Only when the shown days change, not on every tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days.join()]);

  const byDay = useMemo(() => {
    const map = new Map<string, ReturnType<typeof layOut<GridEvent>>>();
    for (const day of days) map.set(day, layOut(events.filter((e) => e.day === day)));
    return map;
  }, [days, events]);
  const hasShifts = shifts.length > 0;
  const hourLabel = (hour: number) => new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "UTC" }).format(new Date(Date.UTC(2000, 0, 1, hour)));

  return (
    <div className="card overflow-hidden p-0">
      <div ref={scroller} className="max-h-[72dvh] overflow-auto overscroll-contain">
        <div className="grid" style={{ gridTemplateColumns: `3.5rem repeat(${days.length}, minmax(${days.length > 1 ? "8.5rem" : "0"}, 1fr))` }}>
          {/* Day headers stay at the top while the hours scroll. */}
          <div className="sticky start-0 top-0 z-30 border-b border-border bg-surface" />
          {days.map((day) => {
            const isToday = now?.day === day;
            return (
              <div key={day} className={`sticky top-0 z-20 flex items-center justify-center gap-2 border-b border-s border-border bg-surface/95 px-2 py-2.5 text-sm backdrop-blur ${isToday ? "text-primary" : ""}`}>
                <span className="text-muted">{formatDay(day, locale, { weekday: "short" })}</span>
                <span className={`flex size-8 items-center justify-center rounded-full text-base font-semibold tabular-nums ${isToday ? "bg-primary text-on-primary" : ""}`}>
                  {formatDay(day, locale, { day: "numeric" })}
                </span>
                {closed[day] !== undefined && (
                  <span className="rounded-full bg-warning/15 px-2 py-0.5 text-xs font-semibold text-foreground" title={closed[day] ?? undefined}>
                    {labels.closed}
                  </span>
                )}
              </div>
            );
          })}

          {/* The hours. */}
          <div className="sticky start-0 z-10 bg-surface" style={{ height }}>
            {hours.map((hour) => (
              <span key={hour} className="absolute end-2 -translate-y-1/2 text-[0.6875rem] tabular-nums text-muted" style={{ top: y(hour * 60) }} dir="ltr">
                {hour * 60 > range.from ? hourLabel(hour) : ""}
              </span>
            ))}
            {now && days.includes(now.day) && now.minutes >= range.from && now.minutes <= range.to && (
              <span className="absolute end-1 z-10 -translate-y-1/2 rounded-full bg-danger px-1.5 py-px text-[0.625rem] font-semibold tabular-nums text-white" style={{ top: y(now.minutes) }} dir="ltr">
                <span className="sr-only">{labels.now} </span>
                {clock(now.minutes)}
              </span>
            )}
          </div>

          {days.map((day) => {
            const placed = byDay.get(day) ?? [];
            const dayShifts = shifts.filter((s) => s.day === day);
            const isClosed = closed[day] !== undefined;
            const openings = open?.[day];
            return (
              <div
                key={day}
                aria-label={formatDay(day, locale, { weekday: "long", day: "numeric", month: "long" })}
                role="group"
                className={`relative border-s border-border ${isClosed ? "bg-[repeating-linear-gradient(135deg,transparent_0_8px,color-mix(in_oklab,var(--foreground)_5%,transparent)_8px_16px)]" : ""}`}
                style={{ height }}
              >
                {hours.map((hour) => (
                  <div key={hour} aria-hidden="true" className="absolute inset-x-0 border-t border-border/60" style={{ top: y(hour * 60) }} />
                ))}
                {/* Outside opening hours: a soft shade. */}
                {openings &&
                  !isClosed &&
                  closedSpans(openings, range).map((span) => (
                    <div key={span.start} aria-hidden="true" className="absolute inset-x-0 bg-foreground/[0.035]" style={{ top: y(span.start), height: y(span.end) - y(span.start) }} />
                  ))}
                {placed.length === 0 && dayShifts.length === 0 && days.length === 1 && (
                  <p className="absolute inset-x-0 top-8 text-center text-sm text-muted">{labels.empty}</p>
                )}
                <div className="absolute inset-y-0 start-0" style={{ width: hasShifts ? "calc(100% - 1.75rem)" : "100%" }}>
                  {placed.map((event) => {
                    const top = y(event.start);
                    const tall = y(event.end) - top;
                    return (
                      <Link
                        key={event.id}
                        href={event.href}
                        className={`group absolute z-[1] flex flex-col overflow-hidden rounded-lg border-s-[3px] px-1.5 py-1 text-xs leading-tight shadow-sm outline-offset-1 transition-[box-shadow,transform] duration-150 hover:z-[5] hover:shadow-md focus-visible:z-[5] ${event.cancelled ? "opacity-55" : ""}`}
                        style={{
                          top: top + 1,
                          height: Math.max(tall - 2, 18),
                          insetInlineStart: `calc(${(event.lane / event.lanes) * 100}% + 2px)`,
                          width: `calc(${100 / event.lanes}% - 4px)`,
                          borderInlineStartColor: event.color,
                          background: `color-mix(in oklab, ${event.color} 14%, var(--surface))`,
                        }}
                      >
                        <span className="flex items-center gap-1 font-semibold tabular-nums" dir="ltr">
                          {event.branch && <span aria-hidden="true" className="size-2 shrink-0 rounded-full" style={{ background: event.branch.color }} />}
                          <span className="truncate">{event.time}</span>
                        </span>
                        <span className={`truncate font-medium ${event.cancelled ? "line-through" : ""}`} dir="auto">
                          {event.title}
                        </span>
                        {tall > 52 && event.detail && (
                          <span className="truncate text-muted" dir="auto">
                            {event.detail}
                          </span>
                        )}
                        {tall > 68 && event.branch && (
                          <span className="truncate text-muted" dir="auto">
                            {event.branch.name}
                          </span>
                        )}
                      </Link>
                    );
                  })}
                </div>
                {/* Who works when: a narrow lane at the end of the day. */}
                {hasShifts && (
                  <div aria-label={labels.shifts} className="absolute inset-y-0 end-0 w-7 border-s border-dashed border-border/80">
                    {layOut(dayShifts).map((shift) => (
                      <div
                        key={shift.id}
                        title={`${shift.name} · ${shift.label}`}
                        className={`absolute flex justify-center rounded-md pt-0.5 ${shift.warn ? "bg-warning/20" : "bg-primary/10"}`}
                        style={{
                          top: y(shift.start) + 1,
                          height: Math.max(y(shift.end) - y(shift.start) - 2, 16),
                          insetInlineStart: `${(shift.lane / shift.lanes) * 100}%`,
                          width: `${100 / shift.lanes}%`,
                        }}
                      >
                        <Avatar id={shift.userId} name={shift.name} src={shift.avatar} size="xs" />
                        <span className="sr-only">{`${shift.name} ${shift.label}`}</span>
                      </div>
                    ))}
                  </div>
                )}
                {now?.day === day && now.minutes >= range.from && now.minutes <= range.to && (
                  <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 z-[6] flex items-center" style={{ top: y(now.minutes) - 1 }}>
                    <span className="-ms-1 size-2.5 rounded-full bg-danger shadow-[0_0_0_3px_color-mix(in_oklab,var(--danger)_25%,transparent)]" />
                    <span className="h-0.5 flex-1 bg-danger" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const clock = (minutes: number) => `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;

/** The parts of the visible hours outside the opening intervals. */
function closedSpans(openings: { start: number; end: number }[], range: { from: number; to: number }) {
  const spans: { start: number; end: number }[] = [];
  let cursor = range.from;
  for (const interval of [...openings].sort((a, b) => a.start - b.start)) {
    if (interval.start > cursor) spans.push({ start: cursor, end: Math.min(interval.start, range.to) });
    cursor = Math.max(cursor, interval.end);
  }
  if (cursor < range.to) spans.push({ start: cursor, end: range.to });
  return spans.filter((s) => s.end > s.start);
}
