import assert from "node:assert/strict";
import { test } from "node:test";

import { googleMapsLink, wazeLink } from "./maps.ts";

test("links go to the exact point when the branch has one", () => {
  const point = { latitude: 32.0853, longitude: 34.7818 };
  assert.equal(wazeLink("Dizengoff 1, Tel Aviv", point), "https://waze.com/ul?ll=32.0853,34.7818&navigate=yes");
  assert.equal(googleMapsLink("Dizengoff 1, Tel Aviv", point), "https://www.google.com/maps/dir/?api=1&destination=32.0853,34.7818");
});

test("links fall back to the address without a point", () => {
  assert.equal(wazeLink("Dizengoff 1"), "https://waze.com/ul?q=Dizengoff%201&navigate=yes");
  assert.equal(googleMapsLink("Dizengoff 1", { latitude: null, longitude: 34 }), "https://www.google.com/maps/dir/?api=1&destination=Dizengoff%201");
});
