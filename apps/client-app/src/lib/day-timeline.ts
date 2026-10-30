export type TimelineSession = { id: string; starts_at: string; ends_at: string; status: string };

export type TimelineState = "past" | "live" | "upcoming";

export type TimelineItem<S extends TimelineSession> =
  | { kind: "hour"; key: string; hour: number }
  | { kind: "session"; key: string; session: S; state: TimelineState }
  | { kind: "now"; key: string };

/** Hour of day (0-23) of an instant in the business's time zone. */
export function hourOf(instant: string, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone }).formatToParts(new Date(instant));
  return Number(parts.find((p) => p.type === "hour")?.value ?? 0);
}

/** One day's sessions as a timeline: an hour heading before each hour that has sessions, and, when the
 * day is today (`nowMs` given), a "now" marker between what has started and what is still ahead.
 * A session is past once it ended, live while it runs; cancelled ones never count as live. */
export function buildTimeline<S extends TimelineSession>(sessions: S[], timeZone: string, nowMs: number | null): TimelineItem<S>[] {
  const sorted = [...sessions].sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const items: TimelineItem<S>[] = [];
  let hour = -1;
  let marked = nowMs === null;
  for (const session of sorted) {
    const startsAt = Date.parse(session.starts_at);
    const h = hourOf(session.starts_at, timeZone);
    const newHour = h !== hour;
    if (!marked && startsAt > (nowMs as number)) {
      items.push({ kind: "now", key: "now" });
      marked = true;
    }
    if (newHour) {
      hour = h;
      items.push({ kind: "hour", key: `h${h}`, hour: h });
    }
    const ended = Date.parse(session.ends_at) <= (nowMs ?? 0);
    const state: TimelineState = nowMs === null ? "upcoming" : ended ? "past" : startsAt <= nowMs && session.status !== "cancelled" ? "live" : "upcoming";
    items.push({ kind: "session", key: session.id, session, state });
  }
  if (!marked && sorted.length > 0) items.push({ kind: "now", key: "now" });
  return items;
}

/**
 * The session the "now" card is about: the one running (the earliest, when two overlap), or else the next
 * one that has not started. Cancelled sessions never count. Null when the day is over or empty.
 */
export function focusSession<S extends TimelineSession>(sessions: S[], nowMs: number): { session: S; live: boolean } | null {
  const open = sessions.filter((s) => s.status !== "cancelled" && Date.parse(s.ends_at) > nowMs).sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const live = open.find((s) => Date.parse(s.starts_at) <= nowMs);
  if (live) return { session: live, live: true };
  return open[0] ? { session: open[0], live: false } : null;
}
