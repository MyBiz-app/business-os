import { describe, expect, it } from "vitest";

import type { BranchSpot } from "../branch-map/planned-core";

import { cards, type Area } from "./insights-core";

const area = (code: number, name: string, latitude: number | null, longitude: number | null, more: Partial<Area> = {}): Area => ({
  code,
  name,
  latitude,
  longitude,
  clients: 0,
  newClients: 0,
  leads: 0,
  leadsWon: 0,
  ...more,
});

// Tel Aviv, Ramat Gan (about 5 km away), Kiryat Shmona (far north).
const telAviv = area(5000, "Tel Aviv", 32.08, 34.78, { clients: 6, leads: 2, leadsWon: 1 });
const ramatGan = area(8600, "Ramat Gan", 32.07, 34.82, { clients: 3 });
const kiryatShmona = area(2800, "Kiryat Shmona", 33.21, 35.57, { clients: 1, leads: 4, leadsWon: 3 });
const unplaced = area(1, "Nowhere", null, null, { clients: 2 });
const branch: BranchSpot = { id: "b", name: "Studio", cityCode: 5000, latitude: 32.08, longitude: 34.78 };

describe("insights cards", () => {
  it("ranks cities by clients and shows each share of all clients", () => {
    const { topCities } = cards([ramatGan, kiryatShmona, telAviv, unplaced], [branch]);
    expect(topCities.map((c) => c.name)).toEqual(["Tel Aviv", "Ramat Gan", "Nowhere", "Kiryat Shmona"]);
    expect(topCities[0].share).toBeCloseTo(6 / 12);
  });

  it("counts the share of clients within 10 km of a branch among those with a known city centre", () => {
    const { within } = cards([telAviv, ramatGan, kiryatShmona, unplaced], [branch]);
    expect(within).toMatchObject({ km: 10, clients: 9, placed: 10 });
    expect(within?.share).toBeCloseTo(0.9);
  });

  it("has no reach numbers without a branch on the map", () => {
    expect(cards([telAviv], []).within).toBeNull();
  });

  it("finds white spots: cities with leads and no branch within 10 km, one far lead included", () => {
    const { whiteSpots } = cards([telAviv, kiryatShmona, area(7, "Far", 29.55, 34.95, { leads: 1 })], [branch]);
    expect(whiteSpots.map((s) => [s.name, s.leads])).toEqual([["Kiryat Shmona", 4], ["Far", 1]]);
  });

  it("lists every lead city as a white spot when there is no branch yet", () => {
    expect(cards([telAviv], []).whiteSpots).toHaveLength(1);
  });

  it("gives the win rate of leads by city", () => {
    const { conversion } = cards([telAviv, kiryatShmona], [branch]);
    expect(conversion.map((c) => [c.name, c.rate])).toEqual([["Kiryat Shmona", 0.75], ["Tel Aviv", 0.5]]);
  });
});
