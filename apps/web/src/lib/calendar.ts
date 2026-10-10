/** Calendar geometry: where events sit on a day's time grid and how overlapping ones share it.
 * Pure functions (tested in calendar.test.ts); times are minutes since local midnight. */

/** Minutes since local midnight (in `timeZone`) of an instant. */
export function minutesIn(instant: string | Date, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone, hour: "numeric", minute: "numeric", hourCycle: "h23" }).formatToParts(
    typeof instant === "string" ? new Date(instant) : instant,
  );
  const value = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  return value("hour") * 60 + value("minute");
}

export type Span = { id: string; start: number; end: number };
export type Placed<T extends Span> = T & { lane: number; lanes: number };

/** Lays out overlapping events side by side: each cluster of events that overlap (directly or
 * through others) shares its width equally among as many lanes as it needs. */
export function layOut<T extends Span>(events: T[]): Placed<T>[] {
  const sorted = [...events].sort((a, b) => a.start - b.start || b.end - a.end);
  const placed: Placed<T>[] = [];
  let cluster: Placed<T>[] = [];
  let laneEnds: number[] = [];
  let clusterEnd = -Infinity;
  const close = () => {
    for (const event of cluster) event.lanes = laneEnds.length;
    cluster = [];
    laneEnds = [];
  };
  for (const event of sorted) {
    if (event.start >= clusterEnd) close();
    let lane = laneEnds.findIndex((end) => end <= event.start);
    if (lane === -1) lane = laneEnds.length;
    laneEnds[lane] = event.end;
    const item = { ...event, lane, lanes: 1 };
    cluster.push(item);
    placed.push(item);
    clusterEnd = Math.max(clusterEnd === -Infinity ? event.end : clusterEnd, event.end);
    if (cluster.length === 1) clusterEnd = event.end;
  }
  close();
  return placed;
}

/** The hours the grid shows: from the earliest event or opening (at most 8:00) to the latest
 * (at least 20:00), whole hours, within the day. */
export function visibleHours(spans: { start: number; end: number }[]): { from: number; to: number } {
  const from = Math.min(8 * 60, ...spans.map((s) => s.start));
  const to = Math.max(20 * 60, ...spans.map((s) => s.end));
  return { from: Math.max(0, Math.floor(from / 60) * 60), to: Math.min(24 * 60, Math.ceil(to / 60) * 60) };
}

/** A stable, distinct color per branch (by its position in the business's branch list). */
const BRANCH_COLORS = ["#7c3aed", "#0891b2", "#d97706", "#db2777", "#16a34a", "#2563eb", "#dc2626", "#4f46e5", "#0d9488"];
export function branchColor(index: number): string {
  return BRANCH_COLORS[((index % BRANCH_COLORS.length) + BRANCH_COLORS.length) % BRANCH_COLORS.length];
}
