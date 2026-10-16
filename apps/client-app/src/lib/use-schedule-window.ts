import { addDays } from "@business-os/i18n/dates";
import { unwrap } from "@business-os/app-kit/lib/api";
import { MAX_REQUEST_DAYS, type CalendarView, rangeFor } from "@business-os/app-kit/lib/calendar-range";
import { useCallback, useEffect, useRef, useState } from "react";

import type { ClientSession } from "@/components/session-card";
import { useBusiness } from "@/providers/business-provider";

type Closed = { day: string; reason?: string | null };
type Chunk = { sessions: ClientSession[]; closed: Closed[] };

const EPOCH = "1970-01-01";
const dayNumber = (day: string) => Math.floor(Date.parse(`${day}T00:00:00Z`) / 86_400_000);

/** Fixed 14-day blocks covering a range, so scrolling the strip reuses what was already fetched. */
export function chunkStarts(start: string, days: number): string[] {
  const first = Math.floor(dayNumber(start) / MAX_REQUEST_DAYS);
  const last = Math.floor(dayNumber(addDays(start, days - 1)) / MAX_REQUEST_DAYS);
  return Array.from({ length: last - first + 1 }, (_, i) => addDays(EPOCH, (first + i) * MAX_REQUEST_DAYS));
}

/** Sessions and closed days for what the calendar shows now, fetched in cached blocks. */
export function useScheduleWindow(view: CalendarView, day: string) {
  const { api, scope, business } = useBusiness();
  const [chunks, setChunks] = useState<Record<string, Chunk>>({});
  const [loading, setLoading] = useState(false);
  const pending = useRef(new Set<string>());
  const scopeKey = `${business?.id ?? ""}`;

  // A different business starts from nothing.
  useEffect(() => {
    setChunks({});
    pending.current.clear();
  }, [scopeKey]);

  const fetchChunk = useCallback(
    async (start: string) => {
      const query = { start, days: MAX_REQUEST_DAYS };
      const [sessions, closed] = await Promise.all([
        api.GET("/client/sessions", { params: { ...scope, query } }),
        api.GET("/client/closed-days", { params: { ...scope, query } }),
      ]);
      return { sessions: unwrap(sessions), closed: unwrap(closed) } as Chunk;
    },
    [api, scope],
  );

  useEffect(() => {
    if (!business || !day) return;
    const range = rangeFor(view, day);
    const missing = chunkStarts(range.start, range.days).filter((s) => !chunks[s] && !pending.current.has(s));
    if (missing.length === 0) return;
    missing.forEach((s) => pending.current.add(s));
    setLoading(true);
    void Promise.all(
      missing.map(async (s) => {
        try {
          const chunk = await fetchChunk(s);
          setChunks((current) => ({ ...current, [s]: chunk }));
        } catch {
          // the next move of the calendar retries this block
        } finally {
          pending.current.delete(s);
        }
      }),
    ).finally(() => setLoading(pending.current.size > 0));
  }, [business, day, view, chunks, fetchChunk]);

  const reload = useCallback(() => {
    setChunks({});
    pending.current.clear();
  }, []);

  const all = Object.values(chunks);
  return {
    sessions: all.flatMap((c) => c.sessions),
    closed: all.flatMap((c) => c.closed),
    loading,
    reload,
  };
}
