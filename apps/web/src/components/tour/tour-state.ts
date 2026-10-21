import { useSyncExternalStore } from "react";

let open = 0;
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

/** A tour tells the rest of the page that it is on screen, so nothing else opens a window over it. */
export function registerTour(): () => void {
  open += 1;
  emit();
  return () => {
    open -= 1;
    emit();
  };
}

/** True while a guided tour is showing. */
export function useTourOpen(): boolean {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => open > 0,
    () => false,
  );
}
