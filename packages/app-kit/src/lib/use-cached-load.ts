import { useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { FRESH_MS } from "./query-client";

type CachedLoad<T> = {
  data: T | undefined;
  error: unknown;
  /** True only while there is nothing to show yet, or the person pulled to refresh. */
  loading: boolean;
  /** True while a pull-to-refresh runs (for the pull spinner). */
  refreshing: boolean;
  /** Fetches again now (pull-to-refresh, after a change). */
  reload: () => Promise<void>;
  /** Fetches again right away without a spinner (coming back from a page outside the app). */
  refresh: () => void;
  /** Fetches again only if what is shown is old; for coming back to a screen. Never shows a spinner. */
  revalidate: () => void;
};

/** Like `useLoad`, but the result is kept under `key` (include the person and the business): coming
 * back to a screen shows the last result at once and refreshes it quietly. The result is saved on the
 * device, so it must be plain data (no Map, Set or Date). */
export function useCachedLoad<T>(key: QueryKey, load: () => Promise<T>, options: { enabled?: boolean } = {}): CachedLoad<T> {
  const client = useQueryClient();
  const query = useQuery({ queryKey: key, queryFn: load, enabled: options.enabled ?? true });
  // A new array on every render, but the same key: depend on its text.
  const keyText = JSON.stringify(key);
  const [pulled, setPulled] = useState(false);
  const { refetch } = query;

  const reload = useCallback(async () => {
    setPulled(true);
    try {
      await refetch();
    } finally {
      setPulled(false);
    }
  }, [refetch]);

  const revalidate = useCallback(() => {
    if (options.enabled === false) return;
    void client.fetchQuery({ queryKey: key, queryFn: load, staleTime: FRESH_MS }).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, load, options.enabled, keyText]);

  const refresh = useCallback(() => {
    void client.invalidateQueries({ queryKey: key });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, keyText]);

  return { data: query.data, error: query.error, loading: query.isPending || pulled, refreshing: pulled, reload, refresh, revalidate };
}
