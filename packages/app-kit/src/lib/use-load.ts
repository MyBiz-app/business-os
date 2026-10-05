import { useCallback, useEffect, useState } from "react";

type LoadState<T> = {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  reload: () => Promise<void>;
};

/** Loads data on mount and whenever `load` changes; `reload` powers pull-to-refresh. */
export function useLoad<T>(load: () => Promise<T>): LoadState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<unknown>();
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await load());
      setError(undefined);
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  }, [load]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload };
}
