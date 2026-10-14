import type { components } from "@business-os/api-client";
import { useEffect, useState } from "react";

import { unwrap } from "@business-os/app-kit/lib/api";
import { useBusiness } from "@/providers/business-provider";

export type Location = components["schemas"]["ClientLocation"];

/** The business's branches with their addresses (empty until loaded or when none is set). */
export function useLocations(): Location[] {
  const { api, scope, business } = useBusiness();
  const [locations, setLocations] = useState<Location[]>([]);
  useEffect(() => {
    if (!business) return setLocations([]);
    let active = true;
    void api
      .GET("/client/locations", { params: scope })
      .then(unwrap)
      .then((list) => active && setLocations(list))
      .catch(() => active && setLocations([]));
    return () => {
      active = false;
    };
  }, [api, scope, business]);
  return locations;
}

/** The address to navigate to for a booking at the named branch; a business with a single
 * branch needs no name. */
export function addressOf(locations: Location[], branchName?: string | null): string | null {
  const branch = locations.find((l) => l.name === branchName) ?? (locations.length === 1 ? locations[0] : undefined);
  return branch?.address ?? null;
}
