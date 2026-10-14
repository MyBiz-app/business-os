/** Pure helpers for the class schedule: who teaches, what kind of class, and when the next week opens. */

type Filterable = {
  service: { id: string; name: string };
  instructor?: { id: string; name: string | null } | null;
};

export type ClassFilters = { instructorId: string | null; serviceId: string | null };

export const NO_FILTERS: ClassFilters = { instructorId: null, serviceId: null };

/** The instructors and class types present in the loaded sessions, each once, in first-seen order. */
export function filterOptions<T extends Filterable>(sessions: T[]) {
  const instructors = new Map<string, string>();
  const services = new Map<string, string>();
  for (const s of sessions) {
    services.set(s.service.id, s.service.name);
    if (s.instructor?.name) instructors.set(s.instructor.id, s.instructor.name);
  }
  const list = (map: Map<string, string>) => [...map].map(([id, name]) => ({ id, name }));
  return { instructors: list(instructors), services: list(services) };
}

export function applyFilters<T extends Filterable>(sessions: T[], filters: ClassFilters): T[] {
  return sessions.filter(
    (s) =>
      (!filters.instructorId || s.instructor?.id === filters.instructorId) &&
      (!filters.serviceId || s.service.id === filters.serviceId),
  );
}

/** "Fill" of a class from 0 to 1, for the progress bar ("4/7 spots"). */
export function fillRatio(capacity: number, spotsLeft: number): number {
  return capacity > 0 ? Math.min(Math.max((capacity - spotsLeft) / capacity, 0), 1) : 0;
}

/** The next release moment, only when it is still ahead (weekly release is on). */
export function upcomingRelease(nextReleaseAt: string | null | undefined, now: number): Date | null {
  if (!nextReleaseAt) return null;
  const at = new Date(nextReleaseAt);
  return at.getTime() > now ? at : null;
}
