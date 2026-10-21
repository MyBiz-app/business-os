/** Distances between a person and a business's branches. The person's position is used on their
 * own device only; it is never sent to the API or to any outside service. */
export type GeoPoint = { latitude: number; longitude: number };

const EARTH_RADIUS_KM = 6371;
const rad = (degrees: number) => (degrees * Math.PI) / 180;

/** Great-circle distance in kilometres. */
export function distanceKm(a: GeoPoint, b: GeoPoint): number {
  const dLat = rad(b.latitude - a.latitude);
  const dLon = rad(b.longitude - a.longitude);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.latitude)) * Math.cos(rad(b.latitude)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(h)));
}

type Placed = { latitude?: number | null; longitude?: number | null };

export const hasPoint = <T extends Placed>(place: T): place is T & GeoPoint => place.latitude != null && place.longitude != null;

/** The branches that have a point on the map, nearest first, each with its distance. */
export function byDistance<T extends Placed>(from: GeoPoint, places: T[]): { place: T & GeoPoint; km: number }[] {
  return places
    .filter(hasPoint)
    .map((place) => ({ place, km: distanceKm(from, place) }))
    .sort((x, y) => x.km - y.km);
}

/** "350 m" under a kilometre, "2.4 km" under ten, "12 km" beyond. */
export function distanceLabel(km: number): { unit: "m" | "km"; value: number } {
  if (km < 1) return { unit: "m", value: Math.max(10, Math.round((km * 1000) / 10) * 10) };
  return { unit: "km", value: km < 10 ? Math.round(km * 10) / 10 : Math.round(km) };
}
