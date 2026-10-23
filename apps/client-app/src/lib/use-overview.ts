import type { components } from "@business-os/api-client";
import { useFocusEffect } from "expo-router";
import { useCallback } from "react";

import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

export type ClientOverview = components["schemas"]["ClientOverview"];

/** Everything the person has across the businesses they are a client of (one request, only their
 * own rows). Loaded only for someone with two businesses or more, and refreshed whenever the
 * screen comes back into focus. */
export function useOverview(force = false) {
  const { api, businesses } = useBusiness();
  const wanted = force || (businesses?.length ?? 0) > 1;
  const load = useCallback(async (): Promise<ClientOverview | null> => {
    if (!wanted) return null;
    return unwrap(await api.GET("/client/overview"));
  }, [api, wanted]);
  const state = useLoad(load);
  const { reload } = state;
  useFocusEffect(
    useCallback(() => {
      void reload();
    }, [reload]),
  );
  return state;
}
