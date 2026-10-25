import type { components } from "@business-os/api-client";
import { useCallback, useEffect, useState } from "react";

import { useLoad } from "@business-os/app-kit/lib/use-load";
import { fetchFriendSettings } from "@/lib/client-data";
import { useDataContext } from "@/lib/use-data-context";

export type FriendSettings = components["schemas"]["FriendSettings"];

/** The friends switch for the current business: whether it offers friends, my code, my privacy. */
export function useFriendSettings() {
  const ctx = useDataContext();
  const load = useCallback(async () => (ctx ? fetchFriendSettings(ctx) : null), [ctx]);
  return useLoad<FriendSettings | null>(load);
}

/** Whether the current business offers friends. One request, shared by every class card and the profile. */
export function useFriendsEnabled(): boolean {
  const ctx = useDataContext();
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    if (!ctx) return;
    let live = true;
    fetchFriendSettings(ctx)
      .then((settings) => live && setEnabled(settings.enabled))
      .catch(() => live && setEnabled(false));
    return () => {
      live = false;
    };
  }, [ctx]);
  return enabled;
}
