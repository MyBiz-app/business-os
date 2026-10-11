/** Calendar geometry: where events sit on a day's time grid and how overlapping ones share it.
 * Pure functions (tested in calendar.test.ts); times are minutes since local midnight. */

/** Minutes since local midnight (in `timeZone`) of an instant. */
export function minutesIn(instant: string | Date, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour: "numeric",
    minute: "numeric",
    hourCycle: "h23",
  }).formatToParts(typeof instant === "string" ? new Date(instant) : instant);
  const value = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  return value("hour") * 60 + value("minute");
}

export type Span = { id: string; start: number; end: number };
export type Placed<T extends Span> = T & {
  lane: number;
  lanes: number;
  cluster: number;
};

/** Lays out overlapping events side by side: each cluster of events that overlap (directly or
 * through others) shares its width equally among as many lanes as it needs. */
export function layOut<T extends Span>(events: T[]): Placed<T>[] {
  const sorted = [...events].sort((a, b) => a.start - b.start || b.end - a.end);
  const placed: Placed<T>[] = [];
  let cluster: Placed<T>[] = [];
  let laneEnds: number[] = [];
  let clusterEnd = -Infinity;
  let clusters = 0;
  const close = () => {
    for (const event of cluster) event.lanes = laneEnds.length;
    if (cluster.length) clusters += 1;
    cluster = [];
    laneEnds = [];
  };
  for (const event of sorted) {
    if (event.start >= clusterEnd) close();
    let lane = laneEnds.findIndex((end) => end <= event.start);
    if (lane === -1) lane = laneEnds.length;
    laneEnds[lane] = event.end;
    const item = { ...event, lane, lanes: 1, cluster: clusters };
    cluster.push(item);
    placed.push(item);
    clusterEnd = Math.max(clusterEnd === -Infinity ? event.end : clusterEnd, event.end);
    if (cluster.length === 1) clusterEnd = event.end;
  }
  close();
  return placed;
}

export type More = {
  id: string;
  start: number;
  end: number;
  lane: number;
  lanes: number;
  count: number;
};

/** Keeps a crowded cluster readable: at most `max` lanes, the last of them a "+N more" block
 * over the time the hidden events take. */
export function capLanes<T extends Span>(placed: Placed<T>[], max: number): { shown: Placed<T>[]; more: More[] } {
  const shown: Placed<T>[] = [];
  const hidden = new Map<number, Placed<T>[]>();
  for (const event of placed) {
    if (event.lanes <= max) shown.push(event);
    else if (event.lane < max - 1) shown.push({ ...event, lanes: max });
    else hidden.set(event.cluster, [...(hidden.get(event.cluster) ?? []), event]);
  }
  const more = [...hidden.entries()].map(([cluster, events]) => ({
    id: `more-${cluster}`,
    start: Math.min(...events.map((e) => e.start)),
    end: Math.max(...events.map((e) => e.end)),
    lane: max - 1,
    lanes: max,
    count: events.length,
  }));
  return { shown, more };
}

/** How many spans cover each stretch of the day: consecutive segments with their count (zero
 * stretches left out). */
export function coverage(spans: { start: number; end: number }[]): { start: number; end: number; count: number }[] {
  const edges = [...new Set(spans.flatMap((s) => [s.start, s.end]))].sort((a, b) => a - b);
  const segments: { start: number; end: number; count: number }[] = [];
  for (let i = 0; i < edges.length - 1; i++) {
    const [start, end] = [edges[i], edges[i + 1]];
    const count = spans.filter((s) => s.start <= start && s.end >= end).length;
    const last = segments.at(-1);
    if (count === 0) continue;
    if (last && last.end === start && last.count === count) last.end = end;
    else segments.push({ start, end, count });
  }
  return segments;
}

/** The hours the grid shows: from the earliest event or opening (at most 8:00) to the latest
 * (at least 20:00), whole hours, within the day. */
export function visibleHours(spans: { start: number; end: number }[]): {
  from: number;
  to: number;
} {
  const from = Math.min(8 * 60, ...spans.map((s) => s.start));
  const to = Math.max(20 * 60, ...spans.map((s) => s.end));
  return {
    from: Math.max(0, Math.floor(from / 60) * 60),
    to: Math.min(24 * 60, Math.ceil(to / 60) * 60),
  };
}

/** A stable, distinct color per branch (by its position in the business's branch list). */
const BRANCH_COLORS = ["#7c3aed", "#0891b2", "#d97706", "#db2777", "#16a34a", "#2563eb", "#dc2626", "#4f46e5", "#0d9488"];
export function branchColor(index: number): string {
  return BRANCH_COLORS[((index % BRANCH_COLORS.length) + BRANCH_COLORS.length) % BRANCH_COLORS.length];
}

/** The ranges of the schedule board and how many branches (or other parallel lanes) each shows
 * side by side: a day has the room for the most, a month shows one. */
export type BoardRange = "day" | "week" | "month";

export const LANE_LIMIT: Record<BoardRange, number> = { day: 6, week: 3, month: 1 };

export function isBoardRange(value: unknown): value is BoardRange {
  return value === "day" || value === "week" || value === "month";
}

/** The first picks that fit the range, without repeats. */
export function limitLanes(ids: string[], range: BoardRange): string[] {
  return [...new Set(ids)].slice(0, LANE_LIMIT[range]);
}
