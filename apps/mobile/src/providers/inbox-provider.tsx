import type { components } from "@business-os/api-client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { AppState } from "react-native";

import { unwrap } from "@/lib/api";
import { useBusiness } from "@/providers/business-provider";

export type Inbox = components["schemas"]["Inbox"];

type InboxContextValue = {
  inbox: Inbox | null;
  /** Reloads the inbox and returns it (null if it couldn't load). */
  refresh: () => Promise<Inbox | null>;
  markAllRead: () => Promise<void>;
};

const InboxContext = createContext<InboxContextValue | null>(null);
const POLL_MS = 60_000;

/** The client's notifications in the current business, refreshed every minute and when the
 * app comes back to the foreground. */
export function InboxProvider({ children }: { children: React.ReactNode }) {
  const { api, scope, business } = useBusiness();
  const [inbox, setInbox] = useState<Inbox | null>(null);

  const refresh = useCallback(async () => {
    if (!business) {
      setInbox(null);
      return null;
    }
    try {
      const loaded = unwrap(await api.GET("/client/notifications", { params: scope }));
      setInbox(loaded);
      return loaded;
    } catch {
      return null; // keep the last inbox; the next refresh tries again
    }
  }, [api, scope, business]);

  const markAllRead = useCallback(async () => {
    if (!business) return;
    try {
      setInbox(unwrap(await api.POST("/client/notifications/read", { params: scope, body: {} })));
    } catch {
      // Not critical: they stay unread until the next try.
    }
  }, [api, scope, business]);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), POLL_MS);
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") void refresh();
    });
    return () => {
      clearInterval(timer);
      subscription.remove();
    };
  }, [refresh]);

  return <InboxContext.Provider value={{ inbox, refresh, markAllRead }}>{children}</InboxContext.Provider>;
}

export function useInbox(): InboxContextValue {
  const value = useContext(InboxContext);
  if (!value) throw new Error("useInbox must be used inside InboxProvider");
  return value;
}
