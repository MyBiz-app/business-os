import { type CalendarView, rangeFor } from "@business-os/app-kit/lib/calendar-range";
import { useCallback, useEffect, useRef, useState } from "react";

import { type Chunk, chunkStarts, fetchChunk, forgetChunks, savedChunk } from "@/lib/client-data";
import { useDataContext } from "@/lib/use-data-context";

/** Sessions and closed days for what the calendar shows now, fetched in cached blocks. Blocks
 * already on the device show at once and are refreshed behind them. */
export function useScheduleWindow(view: CalendarView, day: string) {
  const ctx = useDataContext();
  const [chunks, setChunks] = useState<Record<string, Chunk>>({});
  const [loading, setLoading] = useState(false);
  const [version, setVersion] = useState(0);
  const asked = useRef(new Set<string>());
  const scopeKey = `${ctx?.userId ?? ""}:${ctx?.business.id ?? ""}`;

  // A different business starts from nothing.
  useEffect(() => {
    setChunks({});
    asked.current.clear();
  }, [scopeKey]);

  useEffect(() => {
    if (!ctx || !day) return;
    const range = rangeFor(view, day);
    const missing = chunkStarts(range.start, range.days).filter((s) => !asked.current.has(s));
    if (missing.length === 0) return;
    missing.forEach((s) => asked.current.add(s));

    const saved = missing.flatMap((s) => {
      const chunk = savedChunk(ctx, s);
      return chunk ? [[s, chunk] as const] : [];
    });
    if (saved.length > 0) setChunks((current) => ({ ...Object.fromEntries(saved), ...current }));

    // Only blocks with nothing to show yet count as loading.
    let waiting = missing.length - saved.length;
    if (waiting > 0) setLoading(true);
    const seen = new Set(saved.map(([s]) => s));
    missing.forEach((s) => {
      void fetchChunk(ctx, s)
        .then((chunk) => setChunks((current) => ({ ...current, [s]: chunk })))
        // the next move of the calendar retries this block
        .catch(() => asked.current.delete(s))
        .finally(() => {
          if (!seen.has(s)) waiting -= 1;
          if (waiting <= 0) setLoading(false);
        });
    });
  }, [ctx, day, view, version]);

  const reload = useCallback(() => {
    if (ctx) void forgetChunks(ctx);
    setChunks({});
    asked.current.clear();
    setVersion((v) => v + 1);
  }, [ctx]);

  const all = Object.values(chunks);
  return {
    sessions: all.flatMap((c) => c.sessions),
    closed: all.flatMap((c) => c.closed),
    loading,
    reload,
  };
}
