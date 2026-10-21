import "server-only";

import { unwrap } from "@/lib/api";
import { addDays, todayIn } from "@/lib/dates";
import type { getTenant } from "@/lib/tenant";

import type { MapBranch } from "@/components/branch-map/branch-map";
import type { ClientCity } from "@/components/branch-map/planned-core";

type Context = Awaited<ReturnType<typeof getTenant>>;

const DAYS = 30;

/** The branches that can go on the map: active, with a point, with the last 30 completed days of
 * numbers (the same definitions as the reports). Empty without the right to see reports. */
export async function loadBranchMap({ api, scope, tenant }: Pick<Context, "api" | "scope" | "tenant">): Promise<MapBranch[]> {
  if (!tenant.permissions.includes("reports.read")) return [];
  // Branch by branch across the person's branches, not just the one picked in the menu.
  const network = { header: { "X-Tenant-Id": scope.header["X-Tenant-Id"] } };
  const end = addDays(todayIn(tenant.time_zone), -1);
  const start = addDays(end, -(DAYS - 1));

  const locations = unwrap(await api.GET("/locations", { params: network })).filter((l) => l.active && l.latitude !== null && l.longitude !== null);
  if (locations.length === 0) return [];

  const insights = await api
    .GET("/metrics/branch-insights", { params: { ...network, query: { start, end } } })
    .then((r) => r.data ?? null);
  const insightOf = (id: string) => insights?.branches.find((b) => b.location_id === id);

  const canSeeSchedule = tenant.permissions.includes("schedule.read");
  const [rows, today, ...series] = await Promise.all([
    api
      .GET("/metrics/branches", { params: { ...network, query: { start, end, keys: ["revenue", "active_clients", "occupancy", "sessions_held"] } } })
      .then((r) => r.data ?? []),
    canSeeSchedule ? api.GET("/sessions", { params: { ...network, query: { start: todayIn(tenant.time_zone), days: 1 } } }).then((r) => r.data ?? []) : [],
    ...locations.map((location) =>
      api
        .GET("/metrics/{key}/series", {
          params: { header: { ...network.header, "X-Location-Id": location.id }, path: { key: "revenue" }, query: { start, end, grain: "day" } },
        })
        .then((r) => r.data ?? []),
    ),
  ]);

  const now = Date.now();
  const running = new Set(today.filter((s) => s.status === "scheduled" && Date.parse(s.starts_at) <= now && now < Date.parse(s.ends_at)).map((s) => s.location_id));
  const valueOf = (id: string, key: string) => rows.find((row) => row.location_id === id)?.metrics.find((m) => m.key === key)?.value ?? null;

  return locations.map((location, i) => {
    const byDay = new Map(series[i].map((point) => [point.bucket.slice(0, 10), point.value ?? 0]));
    return {
      id: location.id,
      name: location.name,
      city: location.city_name,
      cityCode: location.city_code,
      latitude: location.latitude as number,
      longitude: location.longitude as number,
      revenue: valueOf(location.id, "revenue"),
      clients: valueOf(location.id, "active_clients"),
      occupancy: valueOf(location.id, "occupancy"),
      bookings: valueOf(location.id, "sessions_held"),
      series: Array.from({ length: DAYS }, (_, d) => byDay.get(addDays(start, d)) ?? 0),
      live: running.has(location.id),
      origins: (insightOf(location.id)?.origins ?? []).map((o) => ({ city: o.city_name, clients: o.clients, latitude: o.latitude, longitude: o.longitude })),
      staffCost: insightOf(location.id)?.staff_cost_minor ?? null,
      staffCostMonth: insights?.staff_cost_period ?? null,
      staffCount: insightOf(location.id)?.staff_count ?? 0,
    };
  });
}

/** Where the clients live, by city, for the "planned branch" mode. Null without the right to see
 * reports, or for someone who works in only some of the branches (the clients are the whole
 * business's); the map then simply has no such mode. */
export async function loadClientCities({ api, scope, tenant }: Pick<Context, "api" | "scope" | "tenant">): Promise<{ cities: ClientCity[]; total: number } | null> {
  if (!tenant.permissions.includes("reports.read")) return null;
  const network = { header: { "X-Tenant-Id": scope.header["X-Tenant-Id"] } };
  const found = await api.GET("/metrics/client-cities", { params: network }).then((r) => r.data ?? null);
  if (!found) return null;
  return {
    total: found.clients_total,
    cities: found.cities.map((c) => ({ code: c.city_code, name: c.city_name, clients: c.clients, latitude: c.latitude, longitude: c.longitude })),
  };
}
