import type { components } from "@business-os/api-client";
import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { useLocale } from "use-intl";

import { unwrap } from "@/lib/api";
import { useBusiness } from "@/providers/business-provider";

export type MyHealth = components["schemas"]["MyHealth"];

/** The client's health declaration state in the current business, refreshed when the screen
 * comes back into focus (for example after signing). */
export function useHealth(): MyHealth | null {
  const { api, scope, business } = useBusiness();
  const locale = useLocale() === "en" ? "en" : "he";
  const [health, setHealth] = useState<MyHealth | null>(null);

  useFocusEffect(
    useCallback(() => {
      if (!business) return;
      let active = true;
      api
        .GET("/client/health-declaration", { params: { ...scope, query: { locale } } })
        .then(unwrap)
        .then((result) => active && setHealth(result))
        .catch(() => active && setHealth(null));
      return () => {
        active = false;
      };
    }, [api, scope, business, locale]),
  );
  return health;
}
