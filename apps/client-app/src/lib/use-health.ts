import type { components } from "@business-os/api-client";
import { useFocusEffect } from "expo-router";
import { useLocale } from "use-intl";

import { unwrap } from "@business-os/app-kit/lib/api";
import { useCachedLoad } from "@business-os/app-kit/lib/use-cached-load";
import { dataKey } from "@/lib/client-data";
import { useDataContext } from "@/lib/use-data-context";

export type MyHealth = components["schemas"]["MyHealth"];

/** The session the client tapped "book" on while a declaration was missing: once the declaration
 * is signed, that booking continues by itself. */
export const bookAfterHealth: { sessionId: string | null } = { sessionId: null };

/** Whether the business needs a declaration the client has not given (or that ran out) before booking. */
export function mustDeclare(health: MyHealth | null): boolean {
  return !!health?.required && (health.state === "missing" || health.state === "expired");
}

/** The client's health declaration state in the current business, refreshed when the screen
 * comes back into focus (for example after signing). */
export function useHealth(): MyHealth | null {
  const ctx = useDataContext();
  const locale = useLocale() === "en" ? "en" : "he";
  const { data, error, revalidate } = useCachedLoad(
    ctx ? dataKey(ctx, "health", locale) : ["health"],
    async () => {
      if (!ctx) return null;
      return unwrap(await ctx.api.GET("/client/health-declaration", { params: { ...ctx.scope, query: { locale } } }));
    },
    { enabled: Boolean(ctx) },
  );
  // Coming back to a screen asks again only when what is shown is old; signing the form refreshes it itself.
  useFocusEffect(revalidate);
  return ctx && !error ? (data ?? null) : null;
}
