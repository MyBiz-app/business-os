import { RADII_KM, distanceKm, type BranchSpot, type LngLat } from "../branch-map/planned-core";

/** The numbers beside the insights map. Everything is counted from the city a person lives in and
 * the city's centre, never from an address; inside one business every client and lead counts, with
 * no minimum. */

export type Area = {
  code: number;
  name: string;
  latitude: number | null;
  longitude: number | null;
  clients: number;
  newClients: number;
  leads: number;
  leadsWon: number;
};

export type PlacedArea = Area & LngLat;

const TOP = 5;
/** A city is "far from every branch" beyond the widest reach ring. */
export const FAR_KM = RADII_KM[RADII_KM.length - 1];

export const isPlaced = (area: Area): area is PlacedArea => area.latitude !== null && area.longitude !== null;

const byCount = (count: (a: Area) => number) => (a: Area, b: Area) => count(b) - count(a) || a.name.localeCompare(b.name);

/** Km from a city to the nearest branch, null when there is no branch with a point. */
export function nearestBranchKm(area: LngLat, branches: BranchSpot[]): number | null {
  return branches.length ? Math.min(...branches.map((b) => distanceKm(area, b))) : null;
}

export type Cards = {
  topCities: { code: number; name: string; clients: number; share: number }[];
  /** Clients whose city is within the widest ring of a branch, of the clients we can place. */
  within: { km: number; clients: number; placed: number; share: number } | null;
  /** Cities with leads and no branch within the widest ring, most leads first. */
  whiteSpots: { code: number; name: string; leads: number; clients: number; km: number | null }[];
  /** Cities with leads, with the share that were won, most leads first. */
  conversion: { code: number; name: string; leads: number; won: number; rate: number }[];
};

export function cards(areas: Area[], branches: BranchSpot[]): Cards {
  const clientsTotal = areas.reduce((sum, a) => sum + a.clients, 0);
  const topCities = [...areas]
    .filter((a) => a.clients > 0)
    .sort(byCount((a) => a.clients))
    .slice(0, TOP)
    .map((a) => ({ code: a.code, name: a.name, clients: a.clients, share: clientsTotal > 0 ? a.clients / clientsTotal : 0 }));

  let within: Cards["within"] = null;
  if (branches.length > 0) {
    const placed = areas.filter(isPlaced);
    const placedClients = placed.reduce((sum, a) => sum + a.clients, 0);
    const near = placed.reduce((sum, a) => sum + ((nearestBranchKm(a, branches) ?? Infinity) <= FAR_KM ? a.clients : 0), 0);
    within = { km: FAR_KM, clients: near, placed: placedClients, share: placedClients > 0 ? near / placedClients : 0 };
  }

  const whiteSpots = areas
    .filter(isPlaced)
    .filter((a) => a.leads > 0)
    .map((a) => ({ code: a.code, name: a.name, leads: a.leads, clients: a.clients, km: nearestBranchKm(a, branches) }))
    .filter((a) => a.km === null || a.km > FAR_KM)
    .sort((a, b) => b.leads - a.leads || a.name.localeCompare(b.name))
    .slice(0, TOP);

  const conversion = areas
    .filter((a) => a.leads > 0)
    .sort(byCount((a) => a.leads))
    .slice(0, TOP)
    .map((a) => ({ code: a.code, name: a.name, leads: a.leads, won: a.leadsWon, rate: a.leadsWon / a.leads }));

  return { topCities, within, whiteSpots, conversion };
}
