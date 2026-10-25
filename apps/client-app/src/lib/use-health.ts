import type { components } from "@business-os/api-client";
import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { useLocale } from "use-intl";

import { unwrap } from "@business-os/app-kit/lib/api";
import { useBusiness } from "@/providers/business-provider";

export type MyHealth = components["schemas"]["MyHealth"];

const TTL = 20_000;
const recent = new Map<string, { at: number; request: Promise<MyHealth> }>();

/** Forget what was fetched, so the next read asks the server (after signing a declaration). */
export function invalidateHealth(): void {
  recent.clear();
}

/** The session the client tapped "book" on while a declaration was missing: once the declaration
 * is signed, that booking continues by itself. */
export const bookAfterHealth: { sessionId: string | null } = { sessionId: null };

/** Whether the business needs a declaration the client has not given (or that ran out) before booking. */
export function mustDeclare(health: MyHealth | null): boolean {
  return !!health?.required && (health.state === "missing" || health.state === "expired");
}

/** The client's health declaration state in the current business, refreshed when the screen
 * comes back into focus (for example after signing). Many session cards ask at once, so a read
 * is shared for a few seconds. */
export function useHealth(): MyHealth | null {
  const { api, scope, business } = useBusiness();
  const locale = useLocale() === "en" ? "en" : "he";
  const [health, setHealth] = useState<MyHealth | null>(null);

  useFocusEffect(
    useCallback(() => {
      if (!business) return;
      let active = true;
      const key = `${business.id}:${locale}`;
      const cached = recent.get(key);
      const request =
        cached && Date.now() - cached.at < TTL
          ? cached.request
          : api.GET("/client/health-declaration", { params: { ...scope, query: { locale } } }).then(unwrap);
      if (!cached || request !== cached.request) recent.set(key, { at: Date.now(), request });
      request
        .then((result) => active && setHealth(result))
        .catch(() => {
          recent.delete(key);
          if (active) setHealth(null);
        });
      return () => {
        active = false;
      };
    }, [api, scope, business, locale]),
  );
  return health;
}
