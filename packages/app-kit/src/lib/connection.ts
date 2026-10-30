import { useSyncExternalStore } from "react";

// Whether the app can reach the server. Any answer from the API proves the network is up; a request that
// fails before an answer (no signal, airplane mode) marks it down until something answers again.
let online = true;
const listeners = new Set<() => void>();

export function isOnline(): boolean {
  return online;
}

export function setOnline(next: boolean): void {
  if (next === online) return;
  online = next;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useOnline(): boolean {
  return useSyncExternalStore(subscribe, isOnline, () => true);
}

/** True for what fetch throws when no answer came back (not for a request the app cancelled itself). */
export function isNetworkFailure(error: unknown): boolean {
  return error instanceof TypeError || (error instanceof Error && /network|failed to fetch|load failed/i.test(error.message));
}
