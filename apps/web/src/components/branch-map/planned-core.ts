/** The "planned branch" numbers: how many existing clients live near a spot, how far the nearest
 * branch is and which cities send clients but have no branch. Everything is measured from the
 * client's city and the city's centre (never an address), so it can be recomputed live while the
 * pin is dragged. */

export const RADII_KM = [3, 5, 10] as const;
const EARTH_RADIUS_KM = 6371.0088;
const TOP_CITIES = 6;

export type LngLat = { latitude: number; longitude: number };

export type ClientCity = {
  code: number;
  name: string;
  clients: number;
  latitude: number | null;
  longitude: number | null;
};

export type BranchSpot = LngLat & { id: string; name: string; cityCode: number | null };

export type PlannedResult = {
  radii: { km: number; clients: number; share: number }[];
  /** Clients whose city has a known centre: the base the shares are taken from. */
  placed: number;
  /** Clients with a city we cannot place (or none): not counted in any range. */
  unplaced: number;
  nearest: { id: string; name: string; km: number } | null;
  /** Cities with clients and no branch of their own, most clients first. */
  withoutBranch: { code: number; name: string; clients: number; fromPinKm: number; nearestBranchKm: number | null; latitude: number; longitude: number }[];
};

/** The straight-line (great-circle) distance in km between two points. */
export function distanceKm(a: LngLat, b: LngLat): number {
  const rad = (degrees: number) => (degrees * Math.PI) / 180;
  const dLat = rad(b.latitude - a.latitude);
  const dLon = rad(b.longitude - a.longitude);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.latitude)) * Math.cos(rad(b.latitude)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** A circle of `km` around a point as a closed ring of [lng, lat] pairs (for a map layer). */
export function circleRing(center: LngLat, km: number, steps = 64): [number, number][] {
  const lat = (center.latitude * Math.PI) / 180;
  const ring: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const angle = (i / steps) * 2 * Math.PI;
    const dLat = (km / EARTH_RADIUS_KM) * Math.cos(angle);
    const dLon = ((km / EARTH_RADIUS_KM) * Math.sin(angle)) / Math.cos(lat);
    ring.push([center.longitude + (dLon * 180) / Math.PI, center.latitude + (dLat * 180) / Math.PI]);
  }
  return ring;
}

export function planBranch(pin: LngLat, cities: ClientCity[], branches: BranchSpot[]): PlannedResult {
  const placedCities = cities.filter((c): c is ClientCity & LngLat => c.latitude !== null && c.longitude !== null);
  const placed = placedCities.reduce((sum, c) => sum + c.clients, 0);
  const unplaced = cities.reduce((sum, c) => sum + c.clients, 0) - placed;
  const fromPin = new Map(placedCities.map((c) => [c.code, distanceKm(pin, c)]));

  const radii = RADII_KM.map((km) => {
    const clients = placedCities.reduce((sum, c) => sum + ((fromPin.get(c.code) ?? Infinity) <= km ? c.clients : 0), 0);
    return { km, clients, share: placed > 0 ? clients / placed : 0 };
  });

  let nearest: PlannedResult["nearest"] = null;
  for (const branch of branches) {
    const km = distanceKm(pin, branch);
    if (nearest === null || km < nearest.km) nearest = { id: branch.id, name: branch.name, km };
  }

  const hasBranch = new Set(branches.map((b) => b.cityCode).filter((code): code is number => code !== null));
  const withoutBranch = placedCities
    .filter((c) => !hasBranch.has(c.code))
    .sort((a, b) => b.clients - a.clients || a.name.localeCompare(b.name))
    .slice(0, TOP_CITIES)
    .map((c) => ({
      code: c.code,
      name: c.name,
      clients: c.clients,
      latitude: c.latitude,
      longitude: c.longitude,
      fromPinKm: fromPin.get(c.code) ?? 0,
      nearestBranchKm: branches.length ? Math.min(...branches.map((b) => distanceKm(c, b))) : null,
    }));

  return { radii, placed, unplaced, nearest, withoutBranch };
}
