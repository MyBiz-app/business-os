import type { ApiClient } from "@business-os/api-client";
import { useEffect, useState } from "react";

import { unwrap } from "@business-os/app-kit/lib/api";
import { type Person } from "@/lib/friends";
import { useBusiness } from "@/providers/business-provider";

// One request per class however many blocks show it; a booking change drops the entry.
const cache = new Map<string, Promise<Person[]>>();

// Blocks that ask in the same moment (a day's schedule) share one request for all their classes.
const BATCH_WAIT_MS = 15;
const BATCH_MAX = 60;
type Waiting = { api: ApiClient; scope: { header: { "X-Tenant-Id": string } }; ids: Map<string, { resolve: (rows: Person[]) => void; reject: (error: unknown) => void }> };
let waiting: Waiting | null = null;

function requestPeople(api: ApiClient, scope: Waiting["scope"], sessionId: string): Promise<Person[]> {
  if (waiting && (waiting.api !== api || waiting.ids.size >= BATCH_MAX)) flush();
  if (!waiting) {
    const batch: Waiting = { api, scope, ids: new Map() };
    waiting = batch;
    setTimeout(() => waiting === batch && flush(), BATCH_WAIT_MS);
  }
  const batch = waiting;
  return new Promise((resolve, reject) => batch.ids.set(sessionId, { resolve, reject }));
}

function flush() {
  const batch = waiting;
  waiting = null;
  if (!batch) return;
  const ids = [...batch.ids.keys()];
  void batch.api
    .GET("/client/sessions/participants", { params: { ...batch.scope, query: { session_ids: ids } } })
    .then(unwrap)
    .then((rows) => batch.ids.forEach((waiter, id) => waiter.resolve(rows[id] ?? [])))
    .catch((error) => batch.ids.forEach((waiter) => waiter.reject(error)));
}

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
      request = requestPeople(api, scope, sessionId);
      cache.set(sessionId, request);
    }
    request.then((rows) => live && setPeople(rows)).catch(() => cache.delete(sessionId));
    return () => {
      live = false;
    };
  }, [api, scope, sessionId, enabled, refresh]);
  return people;
}
