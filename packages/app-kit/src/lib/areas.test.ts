import assert from "node:assert/strict";
import { test } from "node:test";

import { areaHome, buildAreas, pickArea } from "./areas.ts";

const owner = { tenant_id: "t1", tenant_name: "Studio", role: "owner" as const };
const studioAsClient = { id: "t1", name: "Studio" };

test("one person can hold every kind of area, even the same business twice", () => {
  const areas = buildAreas({ platformAdmin: true, memberships: [owner], businesses: [studioAsClient] });
  assert.deepEqual(areas.map((a) => a.key), ["platform", "business:t1", "client:t1"]);
  assert.equal(areas[1]?.role, "owner");
});

test("no identity means no area", () => {
  const areas = buildAreas({ platformAdmin: false, memberships: [], businesses: [] });
  assert.deepEqual(areas, []);
  assert.equal(pickArea(areas, null, ["client"]), null);
});

test("the last area used wins, then the first ready one, then the first", () => {
  const areas = buildAreas({ platformAdmin: false, memberships: [owner], businesses: [studioAsClient] });
  assert.equal(pickArea(areas, "business:t1", ["client"])?.key, "business:t1");
  assert.equal(pickArea(areas, "client:gone", ["client"])?.key, "client:t1");
  assert.equal(pickArea(areas, null, [])?.key, "business:t1");
});

test("each area has its own start screen", () => {
  const [platform, business, client] = buildAreas({ platformAdmin: true, memberships: [owner], businesses: [studioAsClient] });
  assert.deepEqual([platform, business, client].map((a) => areaHome(a!)), ["/platform", "/business", "/home"]);
});

test("a team member gets their business's client area, opened only from the switcher", () => {
  const member = { ...owner, client_app: true };
  const areas = buildAreas({ platformAdmin: false, memberships: [member], businesses: [] });
  assert.deepEqual(areas.map((a) => [a.key, !!a.joinOnOpen]), [["business:t1", false], ["client:t1", true]]);
  assert.equal(pickArea(areas, "client:t1", ["client"])?.key, "business:t1");
});

test("no extra client area when already a client or the business has no client app", () => {
  const joined = buildAreas({ platformAdmin: false, memberships: [{ ...owner, client_app: true }], businesses: [studioAsClient] });
  assert.deepEqual(joined.map((a) => [a.key, !!a.joinOnOpen]), [["business:t1", false], ["client:t1", false]]);
  const noApp = buildAreas({ platformAdmin: false, memberships: [{ ...owner, client_app: false }], businesses: [] });
  assert.deepEqual(noApp.map((a) => a.key), ["business:t1"]);
});
