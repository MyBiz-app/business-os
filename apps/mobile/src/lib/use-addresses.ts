import type { components } from "@business-os/api-client";
import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";

import { unwrap } from "@business-os/app-kit/lib/api";
import { useBusiness } from "@/providers/business-provider";

export type Address = components["schemas"]["Address"];

/** The client's active addresses in the current business (#42), refreshed when the screen comes
 * back into focus (for example after adding one). */
export function useAddresses(): Address[] {
  const { api, scope, business } = useBusiness();
  const [addresses, setAddresses] = useState<Address[]>([]);

  useFocusEffect(
    useCallback(() => {
      if (!business) return;
      let active = true;
      api
        .GET("/client/addresses", { params: scope })
        .then(unwrap)
        .then((list) => active && setAddresses(list.filter((a) => a.active)))
        .catch(() => active && setAddresses([]));
      return () => {
        active = false;
      };
    }, [api, scope, business]),
  );
  return addresses;
}
