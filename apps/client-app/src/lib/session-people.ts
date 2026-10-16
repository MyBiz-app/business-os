import { useEffect, useState } from "react";

import { unwrap } from "@business-os/app-kit/lib/api";
import { type Person } from "@/lib/friends";
import { useBusiness } from "@/providers/business-provider";

// One request per class however many blocks show it; a booking change drops the entry.
const cache = new Map<string, Promise<Person[]>>();

/** Drop what we know about a class's participants (after a booking or invite changes them). */
export function forgetSessionPeople(sessionId: string) {
  cache.delete(sessionId);
}

/** Who else is booked into a class (empty where the category keeps no participant lists). */
export function useSessionPeople(sessionId: string, enabled: boolean, refresh: unknown = 0): Person[] {
  const { api, scope } = useBusiness();
  const [people, setPeople] = useState<Person[]>([]);
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    let request = cache.get(sessionId);
    if (!request) {
      request = api
        .GET("/client/sessions/{session_id}/participants", { params: { ...scope, path: { session_id: sessionId } } })
        .then(unwrap);
      cache.set(sessionId, request);
    }
    request.then((rows) => live && setPeople(rows)).catch(() => cache.delete(sessionId));
    return () => {
      live = false;
    };
  }, [api, scope, sessionId, enabled, refresh]);
  return people;
}
