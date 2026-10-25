import type { components } from "@business-os/api-client";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AppState } from "react-native";

import { unwrap } from "@business-os/app-kit/lib/api";
import { useBusiness } from "@/providers/business-provider";

export type Inbox = components["schemas"]["Inbox"];

type InboxContextValue = {
  inbox: Inbox | null;
  /** Reloads the inbox and returns it (null if it couldn't load). With `maxAgeMs`, a copy loaded
   * more recently than that is returned as it is. */
  refresh: (maxAgeMs?: number) => Promise<Inbox | null>;
  markAllRead: () => Promise<void>;
};

const InboxContext = createContext<InboxContextValue | null>(null);
const POLL_MS = 60_000;

/** The client's notifications in the current business, refreshed every minute and when the
 * app comes back to the foreground. */
export function InboxProvider({ children }: { children: React.ReactNode }) {
  const { api, scope, business } = useBusiness();
  const [inbox, setInbox] = useState<Inbox | null>(null);

  const last = useRef<{ at: number; business: string; inbox: Inbox } | null>(null);

  const refresh = useCallback(async (maxAgeMs = 0) => {
    if (!business) {
      setInbox(null);
      return null;
    }
    if (last.current?.business === business.id && Date.now() - last.current.at < maxAgeMs) return last.current.inbox;
    try {
      const loaded = unwrap(await api.GET("/client/notifications", { params: scope }));
      last.current = { at: Date.now(), business: business.id, inbox: loaded };
      setInbox(loaded);
      return loaded;
    } catch {
      return null; // keep the last inbox; the next refresh tries again
    }
  }, [api, scope, business]);

  const markAllRead = useCallback(async () => {
    if (!business) return;
    try {
      const read = unwrap(await api.POST("/client/notifications/read", { params: scope, body: {} }));
      last.current = { at: Date.now(), business: business.id, inbox: read };
      setInbox(read);
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
