import type { components } from "@business-os/api-client";
import { useFocusEffect } from "expo-router";
import { useLocale } from "use-intl";

import { unwrap } from "@business-os/app-kit/lib/api";
import { useCachedLoad } from "@business-os/app-kit/lib/use-cached-load";
import { dataKey } from "@/lib/client-data";
import { useDataContext } from "@/lib/use-data-context";

export type MyHealth = components["schemas"]["MyHealth"];

/** The client's health declaration state in the current business, refreshed when the screen
 * comes back into focus (for example after signing). */
export function useHealth(): MyHealth | null {
  const ctx = useDataContext();
  const locale = useLocale() === "en" ? "en" : "he";
  const { data, error, refresh } = useCachedLoad(
    ctx ? dataKey(ctx, "health", locale) : ["health"],
    async () => {
      if (!ctx) return null;
      return unwrap(await ctx.api.GET("/client/health-declaration", { params: { ...ctx.scope, query: { locale } } }));
    },
    { enabled: Boolean(ctx) },
  );
  // Signing the form happens on another screen: coming back shows the new state.
  useFocusEffect(refresh);
  return ctx && !error ? (data ?? null) : null;
}
