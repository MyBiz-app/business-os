"use client";

import { Users } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { Avatar } from "@/components/avatar";
import { capLanes, coverage, layOut, minutesIn, visibleHours } from "@/lib/calendar";
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
  /** The lane (branch) id it belongs to when lanes are shown; the first lane when empty. */
  laneId?: string | null;
  /** Shown when several branches share one column without lanes. */
  branch: { name: string; color: string } | null;
  cancelled: boolean;
};

/** A parallel group of columns under every day: a branch today, a court or a person tomorrow. */
export type GridLane = { id: string; name: string; color: string };

export type GridShift = {
  id: string;
  day: string;
  laneId?: string | null;
  start: number;
  end: number;
  userId: string;
  name: string;
  avatar: string | null;
  label: string;
  warn: boolean;
};

type Props = {
  days: string[];
  timeZone: string;
  locale: string;
  events: GridEvent[];
  shifts: GridShift[];
  /** Two or more lanes put each day's columns side by side, each under its own named header. */
  lanes?: GridLane[];
  closed: Record<string, string | null>;
  /** Opening intervals (minutes) per lane id (`""` without lanes) and day; none: not shaded. */
  open: Record<string, Record<string, { start: number; end: number }[]>> | null;
  labels: {
    now: string;
    closed: string;
    shifts: string;
    empty: string;
    more: string;
    onShift: string;
  };
  /** The day view's address with `__day__` for the day: where "+N more" leads from the week. */
  dayHref: string | null;
};

const HOUR = 64; // pixels per hour

/** The day or week as a time grid: events where they happen, overlapping ones side by side,
 * shifts in a narrow lane, closed hours shaded and a live line at the current time. */
export function TimeGrid({ days, timeZone, locale, events, shifts, lanes = [], closed, open, labels, dayHref }: Props) {
  const laned = lanes.length > 1;
  const columns: (GridLane | null)[] = laned ? lanes : [null];
  const range = useMemo(() => visibleHours([...events, ...shifts, ...Object.values(open ?? {}).flatMap((byDay) => Object.values(byDay).flat())].filter((e) => e.end > e.start)), [events, shifts, open]);
  const height = ((range.to - range.from) / 60) * HOUR;
  const y = (minutes: number) => ((minutes - range.from) / 60) * HOUR;
  const hours = Array.from({ length: (range.to - range.from) / 60 }, (_, i) => range.from / 60 + i);

  // The current time, refreshed every 30 seconds (the server's "now" may be stale by then).
  const [now, setNow] = useState<{ day: string; minutes: number } | null>(null);
  useEffect(() => {
    const tick = () =>
      setNow({
        day: todayIn(timeZone),
        minutes: minutesIn(new Date(), timeZone),
      });
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
    const target = days.includes(today) ? minutesIn(new Date(), timeZone) - 90 : Math.min(...events.map((e) => e.start), range.to) - 30;
    element.scrollTop = Math.max(0, y(target));
    // Only when the shown days change, not on every tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days.join()]);

  // A cell is one lane of one day. Room for side-by-side events depends on how wide it is.
  const max = laned ? (days.length > 1 ? 2 : 4) : days.length > 1 ? 3 : 6;
  const laneOf = (item: { laneId?: string | null }) => (laned ? (lanes.some((l) => l.id === item.laneId) ? item.laneId : lanes[0].id) : "");
  const cells = useMemo(() => {
    const map = new Map<string, ReturnType<typeof capLanes<GridEvent>>>();
    for (const day of days)
      for (const lane of columns) {
        const id = lane?.id ?? "";
        const own = events.filter((e) => e.day === day && laneOf(e) === id);
        map.set(`${day}|${id}`, capLanes(layOut(own), max));
      }
    return map;
    // `columns` and `laneOf` follow `lanes`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days, events, lanes, max]);
  const hasShifts = shifts.length > 0;
  const hourLabel = (hour: number) =>
    new Intl.DateTimeFormat(locale, {
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
      timeZone: "UTC",
    }).format(new Date(Date.UTC(2000, 0, 1, hour)));
  const minWidth = laned ? (days.length > 1 ? "7.5rem" : "10rem") : days.length > 1 ? "8.5rem" : "0";
  const dayHeader = "h-11";
  const nowVisible = (day: string) => now?.day === day && now.minutes >= range.from && now.minutes <= range.to;

  return (
    <div className="card overflow-hidden p-0">
      <div ref={scroller} className="max-h-[72dvh] overflow-auto overscroll-contain">
        <div className="grid" style={{ gridTemplateColumns: `3.5rem repeat(${days.length * columns.length}, minmax(${minWidth}, 1fr))` }}>
          {/* Headers stay at the top while the hours scroll: the day, and under it the branch. */}
          <div className="sticky start-0 top-0 z-30 border-b border-border bg-surface" style={{ gridRow: laned ? "span 2" : undefined }} />
          {days.map((day) => {
            const isToday = now?.day === day;
            return (
              <div
                key={day}
                className={`sticky top-0 z-20 flex ${dayHeader} items-center justify-center gap-2 border-s-2 border-border bg-surface px-2 text-sm ${laned ? "" : "border-b"} ${isToday ? "text-primary" : ""}`}
                style={{ gridColumn: `span ${columns.length}` }}
              >
                <span className="text-muted">{formatDay(day, locale, { weekday: laned && days.length === 1 ? "long" : "short" })}</span>
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
          {laned &&
            days.flatMap((day) =>
              lanes.map((lane, index) => (
                <div
                  key={`${day}|${lane.id}`}
                  className={`sticky top-11 z-20 flex items-center gap-1.5 border-b border-t-[3px] border-border bg-surface px-2 py-1.5 text-xs font-semibold ${index === 0 ? "border-s-2" : "border-s"}`}
                  style={{ borderTopColor: lane.color }}
                  title={lane.name}
                >
                  <span aria-hidden="true" className="size-2 shrink-0 rounded-full" style={{ background: lane.color }} />
                  <span className="truncate" dir="auto">
                    {lane.name}
                  </span>
                </div>
              )),
            )}

          {/* The hours. */}
          <div className="sticky start-0 z-10 bg-surface" style={{ height }}>
            {hours.map((hour) => (
              <span key={hour} className="absolute end-2 -translate-y-1/2 text-[0.6875rem] tabular-nums text-muted" style={{ top: y(hour * 60) }} dir="ltr">
                {hour * 60 > range.from ? hourLabel(hour) : ""}
              </span>
            ))}
            {now && days.includes(now.day) && nowVisible(now.day) && (
              <span
                className="absolute end-1 z-10 -translate-y-1/2 rounded-full bg-danger px-1.5 py-px text-[0.625rem] font-semibold tabular-nums text-white"
                style={{ top: y(now.minutes) }}
                dir="ltr"
              >
                <span className="sr-only">{labels.now} </span>
                {clock(now.minutes)}
              </span>
            )}
          </div>

          {days.flatMap((day) =>
            columns.map((lane, laneIndex) => {
              const id = lane?.id ?? "";
              const { shown: placed, more } = cells.get(`${day}|${id}`) ?? { shown: [], more: [] };
              const dayShifts = shifts.filter((s) => s.day === day && laneOf(s) === id);
              const isClosed = closed[day] !== undefined;
              const openings = open?.[id]?.[day];
              return (
                <div
                  key={`${day}|${id}`}
                  aria-label={`${lane ? `${lane.name}, ` : ""}${formatDay(day, locale, { weekday: "long", day: "numeric", month: "long" })}`}
                  role="group"
                  className={`relative ${laneIndex === 0 ? "border-s-2" : "border-s"} border-border ${isClosed ? "bg-[repeating-linear-gradient(135deg,transparent_0_8px,color-mix(in_oklab,var(--foreground)_5%,transparent)_8px_16px)]" : ""}`}
                  style={{ height, background: lane && !isClosed ? `color-mix(in oklab, ${lane.color} 4%, transparent)` : undefined }}
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
                    <p className="absolute inset-x-0 top-8 px-2 text-center text-sm text-muted">{labels.empty}</p>
                  )}
                  <div className="absolute inset-y-0 start-0" style={{ width: hasShifts ? "calc(100% - 2rem)" : "100%" }}>
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
                    {more.map((block) => {
                      const style = {
                        top: y(block.start) + 1,
                        height: Math.max(y(block.end) - y(block.start) - 2, 18),
                        insetInlineStart: `calc(${(block.lane / block.lanes) * 100}% + 2px)`,
                        width: `calc(${100 / block.lanes}% - 4px)`,
                      };
                      const className = "absolute z-[1] flex items-start justify-center rounded-lg border border-dashed border-border bg-surface pt-1 text-xs font-semibold text-muted";
                      const text = labels.more.replace("{count}", String(block.count));
                      return dayHref ? (
                        <Link key={block.id} href={dayHref.replace("__day__", day)} className={`${className} hover:border-primary hover:text-primary`} style={style}>
                          {text}
                        </Link>
                      ) : (
                        <span key={block.id} className={className} style={style}>
                          {text}
                        </span>
                      );
                    })}
                  </div>
                  {/* Who works when: a narrow strip at the end of the column (this branch only). */}
                  {hasShifts && (
                    <div aria-label={labels.shifts} className="absolute inset-y-0 end-0 w-8 border-s border-dashed border-border/80">
                      {crowded(dayShifts)
                        ? coverage(dayShifts).map((segment) => {
                            const block = y(segment.end) - y(segment.start);
                            return (
                              <div
                                key={segment.start}
                                title={`${segment.count} · ${labels.onShift}`}
                                className="absolute inset-x-0.5 flex flex-col items-center justify-center gap-px rounded-md text-[0.6875rem] font-semibold tabular-nums"
                                style={{
                                  top: y(segment.start) + 1,
                                  height: Math.max(block - 2, 14),
                                  background: `color-mix(in oklab, var(--primary) ${Math.min(8 + segment.count * 4, 40)}%, transparent)`,
                                }}
                              >
                                {block > 30 && <Users aria-hidden="true" className="size-3 opacity-70" />}
                                <span aria-hidden="true">{segment.count}</span>
                                <span className="sr-only">{`${segment.count} ${labels.onShift}, ${clock(segment.start)}–${clock(segment.end)}`}</span>
                              </div>
                            );
                          })
                        : layOut(dayShifts).map((shift) => (
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
                  {nowVisible(day) && (
                    <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 z-[6] flex items-center" style={{ top: y(now!.minutes) - 1 }}>
                      <span className="-ms-1 size-2.5 rounded-full bg-danger shadow-[0_0_0_3px_color-mix(in_oklab,var(--danger)_25%,transparent)]" />
                      <span className="h-0.5 flex-1 bg-danger" />
                    </div>
                  )}
                </div>
              );
            }),
          )}
        </div>
      </div>
    </div>
  );
}

const clock = (minutes: number) => `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;

/** More than two people at once don't fit the shifts lane by face: show how many instead. */
const crowded = (shifts: GridShift[]) => layOut(shifts).some((shift) => shift.lanes > 2);

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
