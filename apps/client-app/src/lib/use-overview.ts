import type { components } from "@business-os/api-client";
import { useFocusEffect } from "expo-router";

import { unwrap } from "@business-os/app-kit/lib/api";
import { useCachedLoad } from "@business-os/app-kit/lib/use-cached-load";
import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useBusiness } from "@/providers/business-provider";

export type ClientOverview = components["schemas"]["ClientOverview"];

/** Everything the person has across the businesses they are a client of (one request, only their
 * own rows). Loaded only for someone with two businesses or more, and refreshed whenever the
 * screen comes back into focus. */
export function useOverview(force = false) {
  const { api, businesses } = useBusiness();
  const { session } = useSession();
  const wanted = force || (businesses?.length ?? 0) > 1;
  const state = useCachedLoad(
    [session?.user.id ?? "", "overview", wanted],
    async (): Promise<ClientOverview | null> => (wanted ? unwrap(await api.GET("/client/overview")) : null),
  );
  useFocusEffect(state.revalidate);
  return state;
}
