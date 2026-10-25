import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { useEffect, useRef, type ReactNode } from "react";

import { forgetPictures } from "../components/auth-image";
import { clearQueryCache, KEEP_MS, queryClient, queryPersister } from "../lib/query-client";
import { useSession } from "./session-provider";

// Bump when the shape of saved data changes: older saved data is then dropped, not read.
const CACHE_VERSION = "1";

/** The data cache every screen shares, saved on the device so the next open starts from what was
 * seen last. It belongs to one person: signing out, or signing in as someone else, wipes it. */
export function QueryProvider({ children }: { children: ReactNode }) {
  const { session, loading } = useSession();
  const userId = session?.user.id ?? null;
  const owner = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    if (loading) return;
    if (owner.current !== undefined && owner.current !== userId) {
      void clearQueryCache();
      forgetPictures();
    }
    owner.current = userId;
  }, [userId, loading]);

  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister: queryPersister,
        maxAge: KEEP_MS,
        buster: CACHE_VERSION,
        dehydrateOptions: { shouldDehydrateQuery: (query) => query.state.status === "success" && query.meta?.persist !== false },
      }}
    >
      {children}
    </PersistQueryClientProvider>
  );
}
