import type { components } from "@business-os/api-client";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useCallback, useEffect, useState } from "react";

import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

export type FriendSettings = components["schemas"]["FriendSettings"];

/** The friends switch for the current business: whether it offers friends, my code, my privacy. */
export function useFriendSettings() {
  const { api, scope, business } = useBusiness();
  const load = useCallback(async () => {
    if (!business) return null;
    return unwrap(await api.GET("/client/friends/settings", { params: scope }));
  }, [api, scope, business]);
  return useLoad<FriendSettings | null>(load);
}

const enabledCache = new Map<string, Promise<boolean>>();

/** Whether the current business offers friends. One request per business, shared by every class card. */
export function useFriendsEnabled(): boolean {
  const { api, scope, business } = useBusiness();
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    if (!business) return;
    let cached = enabledCache.get(business.id);
    if (!cached) {
      cached = api
        .GET("/client/friends/settings", { params: scope })
        .then((r) => unwrap(r).enabled)
        .catch(() => false);
      enabledCache.set(business.id, cached);
    }
    let live = true;
    void cached.then((value) => live && setEnabled(value));
    return () => {
      live = false;
    };
  }, [api, scope, business]);
  return enabled;
}
