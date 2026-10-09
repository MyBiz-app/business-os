import type { components } from "@business-os/api-client";
import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";

import { unwrap } from "@business-os/app-kit/lib/api";
import { useBusiness } from "@/providers/business-provider";

export type Dependent = components["schemas"]["Dependent"];

/** The client's active pets / children in the current business (empty when the industry keeps
 * none), refreshed when the screen comes back into focus (for example after adding one). */
export function useDependents(): Dependent[] {
  const { api, scope, business } = useBusiness();
  const [dependents, setDependents] = useState<Dependent[]>([]);

  useFocusEffect(
    useCallback(() => {
      if (!business?.dependents) {
        setDependents([]);
        return;
      }
      let active = true;
      api
        .GET("/client/dependents", { params: scope })
        .then(unwrap)
        .then((list) => active && setDependents(list.filter((d) => d.active)))
        .catch(() => active && setDependents([]));
      return () => {
        active = false;
      };
    }, [api, scope, business]),
  );
  return dependents;
}
