import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { circleRing, distanceKm, planBranch, type BranchSpot, type ClientCity } from "../components/branch-map/planned-core.ts";

const TEL_AVIV = { latitude: 32.0809, longitude: 34.7806 };
const JERUSALEM = { latitude: 31.7683, longitude: 35.2137 };
const RAMAT_GAN = { latitude: 32.0823, longitude: 34.8107 };
const HOLON = { latitude: 32.0103, longitude: 34.7792 };

const cities: ClientCity[] = [
  { code: 5000, name: "Tel Aviv", clients: 40, ...TEL_AVIV },
  { code: 8600, name: "Ramat Gan", clients: 20, ...RAMAT_GAN },
  { code: 6600, name: "Holon", clients: 10, ...HOLON },
  { code: 3000, name: "Jerusalem", clients: 5, ...JERUSALEM },
  { code: 1, name: "Somewhere small", clients: 3, latitude: null, longitude: null },
];
const branches: BranchSpot[] = [{ id: "b1", name: "Tel Aviv studio", cityCode: 5000, ...TEL_AVIV }];

describe("distanceKm", () => {
  it("knows Tel Aviv to Jerusalem is about 54 km", () => {
    const km = distanceKm(TEL_AVIV, JERUSALEM);
    assert.ok(km > 52 && km < 57, String(km));
  });

  it("is zero for the same point", () => {
    assert.equal(distanceKm(TEL_AVIV, TEL_AVIV), 0);
  });
});

describe("circleRing", () => {
  it("is closed and every point is the radius away", () => {
    const ring = circleRing(TEL_AVIV, 5);
    assert.deepEqual(ring[0], ring[ring.length - 1]);
    for (const [longitude, latitude] of ring) assert.ok(Math.abs(distanceKm(TEL_AVIV, { latitude, longitude }) - 5) < 0.05);
  });
});

describe("planBranch", () => {
  it("counts clients within 3, 5 and 10 km of the pin, from the cities' centres", () => {
    const plan = planBranch(TEL_AVIV, cities, branches);
    assert.deepEqual(plan.radii.map((r) => [r.km, r.clients]), [[3, 60], [5, 60], [10, 70]]);
    assert.equal(plan.placed, 75);
    assert.ok(Math.abs(plan.radii[2].share - 70 / 75) < 1e-9);
  });

  it("keeps clients of a city it cannot place out of every range and says how many", () => {
    const plan = planBranch(TEL_AVIV, cities, branches);
    assert.equal(plan.unplaced, 3);
  });

  it("follows the pin: a spot in Jerusalem sees only Jerusalem's clients", () => {
    const plan = planBranch(JERUSALEM, cities, branches);
    assert.deepEqual(plan.radii.map((r) => r.clients), [5, 5, 5]);
  });

  it("finds the nearest branch and its distance", () => {
    const plan = planBranch(RAMAT_GAN, cities, branches);
    assert.equal(plan.nearest?.id, "b1");
    assert.ok(Math.abs((plan.nearest?.km ?? 0) - distanceKm(RAMAT_GAN, TEL_AVIV)) < 1e-9);
  });

  it("has no nearest branch when there are none", () => {
    const plan = planBranch(TEL_AVIV, cities, []);
    assert.equal(plan.nearest, null);
    assert.equal(plan.withoutBranch[0].nearestBranchKm, null);
  });

  it("lists the cities that send clients and have no branch, most clients first", () => {
    const plan = planBranch(HOLON, cities, branches);
    assert.deepEqual(plan.withoutBranch.map((c) => [c.name, c.clients]), [["Ramat Gan", 20], ["Holon", 10], ["Jerusalem", 5]]);
    const ramatGan = plan.withoutBranch[0];
    assert.ok(Math.abs(ramatGan.nearestBranchKm! - distanceKm(RAMAT_GAN, TEL_AVIV)) < 1e-9);
    assert.ok(Math.abs(ramatGan.fromPinKm - distanceKm(HOLON, RAMAT_GAN)) < 1e-9);
  });

  it("copes with no clients at all", () => {
    const plan = planBranch(TEL_AVIV, [], branches);
    assert.deepEqual(plan.radii.map((r) => [r.clients, r.share]), [[0, 0], [0, 0], [0, 0]]);
    assert.deepEqual(plan.withoutBranch, []);
  });
});
