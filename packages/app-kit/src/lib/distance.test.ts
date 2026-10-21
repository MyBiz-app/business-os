import assert from "node:assert/strict";
import { test } from "node:test";

import { byDistance, distanceKm, distanceLabel } from "./distance.ts";

const telAviv = { latitude: 32.0853, longitude: 34.7818 };
const jerusalem = { latitude: 31.7683, longitude: 35.2137 };

test("distanceKm matches the known Tel Aviv to Jerusalem distance", () => {
  const km = distanceKm(telAviv, jerusalem);
  assert.ok(km > 53 && km < 57, `got ${km}`);
  assert.equal(distanceKm(telAviv, telAviv), 0);
});

test("byDistance skips branches without a point and sorts nearest first", () => {
  const near = { id: "near", latitude: 32.09, longitude: 34.78 };
  const far = { id: "far", latitude: 31.77, longitude: 35.21 };
  const unplaced = { id: "none", latitude: null, longitude: null };
  assert.deepEqual(byDistance(telAviv, [far, unplaced, near]).map((r) => r.place.id), ["near", "far"]);
});

test("distanceLabel rounds to a friendly size", () => {
  assert.deepEqual(distanceLabel(0.347), { unit: "m", value: 350 });
  assert.deepEqual(distanceLabel(0.001), { unit: "m", value: 10 });
  assert.deepEqual(distanceLabel(2.44), { unit: "km", value: 2.4 });
  assert.deepEqual(distanceLabel(12.6), { unit: "km", value: 13 });
});
