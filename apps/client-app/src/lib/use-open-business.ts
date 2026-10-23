import { router, type Href } from "expo-router";
import { useCallback } from "react";

import { useAreas } from "@/providers/area-provider";
import { useBusiness } from "@/providers/business-provider";

/** Opens one of the person's businesses (its brand, its data) and, if given, a screen inside it.
 * Goes through the areas, so the business is also remembered as the last one used. */
export function useOpenBusiness(): (tenantId: string, then?: Href) => Promise<void> {
  const { areas, switchTo } = useAreas();
  const { select } = useBusiness();
  return useCallback(
    async (tenantId, then) => {
      const key = `client:${tenantId}`;
      if (areas?.some((a) => a.key === key)) await switchTo(key);
      else await select(tenantId);
      if (then) router.navigate(then);
    },
    [areas, switchTo, select],
  );
}
