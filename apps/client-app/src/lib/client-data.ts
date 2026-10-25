import type { ApiClient, components } from "@business-os/api-client";
import { addDays, todayIn } from "@business-os/i18n/dates";
import { MAX_REQUEST_DAYS } from "@business-os/app-kit/lib/calendar-range";
import { unwrap } from "@business-os/app-kit/lib/api";
import { FRESH_MS, queryClient } from "@business-os/app-kit/lib/query-client";

import type { ClientBusiness } from "@/providers/business-provider";

type Entitlement = components["schemas"]["Entitlement"];

/** What the loaders need: who is asking, in which business, through which client. */
export type DataContext = {
  api: ApiClient;
  scope: { header: { "X-Tenant-Id": string } };
  business: ClientBusiness;
  userId: string;
};

/** Everything a screen saves is filed under the person and the business. */
export const dataKey = (c: Pick<DataContext, "userId"> & { business: { id: string } }, ...parts: unknown[]) => [
  c.userId,
  c.business.id,
  ...parts,
];

/** One request per resource however many screens ask for it, and a copy seen a moment ago is reused. */
function shared<T>(c: DataContext, name: string, load: () => Promise<T>, extra: unknown[] = []): Promise<T> {
  return queryClient.fetchQuery({ queryKey: dataKey(c, "get", name, ...extra), queryFn: load, staleTime: FRESH_MS });
}

const orEmpty = <T>(request: Promise<T[]>) => request.catch(() => [] as T[]);

export const fetchBookings = (c: DataContext) =>
  shared(c, "bookings", async () => unwrap(await c.api.GET("/client/bookings", { params: c.scope })));
export const fetchEntitlements = (c: DataContext) =>
  shared(c, "entitlements", async () => unwrap(await c.api.GET("/client/entitlements", { params: c.scope })));
export const fetchPlans = (c: DataContext) =>
  shared(c, "plans", async () => unwrap(await c.api.GET("/client/plans", { params: c.scope })));
export const fetchServices = (c: DataContext) =>
  shared(c, "services", async () => unwrap(await c.api.GET("/client/appointments/services", { params: c.scope })));
export const fetchResources = (c: DataContext) =>
  shared(c, "resources", async () => unwrap(await c.api.GET("/client/resources", { params: c.scope })));
export const fetchPendingReviews = (c: DataContext) =>
  shared(c, "pending-reviews", async () => unwrap(await c.api.GET("/client/reviews/pending", { params: c.scope })));
export const fetchLocations = (c: DataContext) =>
  shared(c, "locations", async () => unwrap(await c.api.GET("/client/locations", { params: c.scope })));
export const fetchQuotes = (c: DataContext) =>
  shared(c, "quotes", async () => unwrap(await c.api.GET("/client/quotes", { params: c.scope })));
export const fetchDocuments = (c: DataContext) =>
  shared(c, "documents", async () => unwrap(await c.api.GET("/client/documents", { params: c.scope })));
export const fetchReceipts = (c: DataContext) =>
  shared(c, "receipts", async () => unwrap(await c.api.GET("/client/receipts", { params: c.scope })));
export const fetchReleasePolicy = (c: DataContext) =>
  shared(c, "schedule-release", async () => unwrap(await c.api.GET("/client/schedule-release", { params: c.scope })));

export const fetchFriendSettings = (c: DataContext) =>
  shared(c, "friend-settings", async () => unwrap(await c.api.GET("/client/friends/settings", { params: c.scope })));
export const fetchIdentity = (c: DataContext) =>
  shared(c, "identity", async () => unwrap(await c.api.GET("/client/identity", { params: c.scope })));

/** Drops a shared copy after the person changed it, so the next read asks the server. */
export const forgetShared = (c: DataContext, name: string) => queryClient.invalidateQueries({ queryKey: dataKey(c, "get", name) });

/** The sessions of a window of days starting at `start` (at most 14). */
export const fetchSessions = (c: DataContext, start: string, days: number) =>
  shared(c, "sessions", async () => unwrap(await c.api.GET("/client/sessions", { params: { ...c.scope, query: { start, days } } })), [start, days]);
/** The next two weeks of classes: the home screen, the bookings list and the schedule all read them. */
export const fetchUpcomingSessions = (c: DataContext) => fetchSessions(c, todayIn(c.business.time_zone), 14);

type Closed = { day: string; reason?: string | null };
export type Chunk = { sessions: components["schemas"]["ClientSession"][]; closed: Closed[] };

const EPOCH = "1970-01-01";
const dayNumber = (day: string) => Math.floor(Date.parse(`${day}T00:00:00Z`) / 86_400_000);

/** Fixed 14-day blocks covering a range, so scrolling the strip reuses what was already fetched. */
export function chunkStarts(start: string, days: number): string[] {
  const first = Math.floor(dayNumber(start) / MAX_REQUEST_DAYS);
  const last = Math.floor(dayNumber(addDays(start, days - 1)) / MAX_REQUEST_DAYS);
  return Array.from({ length: last - first + 1 }, (_, i) => addDays(EPOCH, (first + i) * MAX_REQUEST_DAYS));
}

const chunkKey = (c: DataContext, start: string) => dataKey(c, "chunk", start);

/** Sessions and closed days of one block. */
export const fetchChunk = (c: DataContext, start: string): Promise<Chunk> =>
  queryClient.fetchQuery({
    queryKey: chunkKey(c, start),
    staleTime: FRESH_MS,
    queryFn: async () => {
      const query = { start, days: MAX_REQUEST_DAYS };
      const [sessions, closed] = await Promise.all([
        c.api.GET("/client/sessions", { params: { ...c.scope, query } }),
        c.api.GET("/client/closed-days", { params: { ...c.scope, query } }),
      ]);
      return { sessions: unwrap(sessions), closed: unwrap(closed) };
    },
  });

/** A block already on the device (possibly old; it is shown at once and refreshed behind it). */
export const savedChunk = (c: DataContext, start: string) => queryClient.getQueryData<Chunk>(chunkKey(c, start));

/** Makes the next look at the schedule fetch again (pull-to-refresh). */
export const forgetChunks = (c: DataContext) => queryClient.invalidateQueries({ queryKey: dataKey(c, "chunk") });

export const homeKey = (c: DataContext) => dataKey(c, "home");
export const bookingsKey = (c: DataContext) => dataKey(c, "bookings-screen");
export const scheduleKey = (c: DataContext) => dataKey(c, "schedule-static");

export async function loadHome(c: DataContext) {
  const [bookings, sessions, entitlements, services, pending, courts] = await Promise.all([
    fetchBookings(c),
    fetchUpcomingSessions(c),
    orEmpty(fetchEntitlements(c)),
    orEmpty(fetchServices(c)),
    orEmpty(fetchPendingReviews(c)),
    orEmpty(fetchResources(c)),
  ]);
  return { bookings, sessions, entitlements, appointments: services.length, courts: courts.length, toReview: pending };
}

const CURRENT = new Set<Entitlement["state"]>(["active", "upcoming", "frozen"]);

export async function loadBookings(c: DataContext) {
  const [all, entitlements, plans, sessions] = await Promise.all([
    fetchBookings(c),
    fetchEntitlements(c),
    fetchPlans(c),
    // Only to learn where each upcoming booking takes place (navigation).
    orEmpty(fetchUpcomingSessions(c)),
  ]);
  const now = Date.now();
  return {
    upcoming: all.filter((b) => Date.parse(b.starts_at) >= now && b.status !== "cancelled").reverse(),
    past: all.filter((b) => Date.parse(b.starts_at) < now || b.status === "cancelled"),
    current: entitlements.filter((e) => CURRENT.has(e.state)),
    plans,
    branchOf: Object.fromEntries(sessions.map((x) => [x.id, x.location_name])) as Record<string, string | null>,
  };
}

export async function loadScheduleStatic(c: DataContext) {
  const [appointments, courts, release] = await Promise.all([
    orEmpty(fetchServices(c)),
    orEmpty(fetchResources(c)),
    fetchReleasePolicy(c).catch(() => null),
  ]);
  return { appointments, courts, release };
}

/** Warms what the other tabs show, so moving to them needs no waiting. Never throws. */
export function prefetchTabs(c: DataContext): void {
  const warm = <T>(key: unknown[], load: () => Promise<T>) =>
    void queryClient.prefetchQuery({ queryKey: key, queryFn: load, staleTime: FRESH_MS });
  warm(bookingsKey(c), () => loadBookings(c));
  warm(scheduleKey(c), () => loadScheduleStatic(c));
  const [thisBlock] = chunkStarts(todayIn(c.business.time_zone), 1);
  if (thisBlock) void fetchChunk(c, thisBlock).catch(() => undefined);
  warm(dataKey(c, "locations-list"), () => fetchLocations(c));
}
