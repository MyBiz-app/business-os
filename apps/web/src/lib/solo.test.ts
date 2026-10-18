import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { isSolo, SOLO_DASHBOARD_TILES, SOLO_MAX_UPGRADES, visibleTopics } from "./solo.ts";

describe("isSolo", () => {
  it("is true only for the solo size", () => {
    assert.equal(isSolo({ business_size: "solo" }), true);
    for (const size of ["small", "medium", "network", null, undefined]) {
      assert.equal(isSolo({ business_size: size }), false);
    }
    assert.equal(isSolo({}), false);
  });
});

describe("solo mode limits", () => {
  it("offers at most two upgrades and a three-tile dashboard", () => {
    assert.equal(SOLO_MAX_UPGRADES, 2);
    assert.deepEqual([...SOLO_DASHBOARD_TILES], ["revenue", "new_clients", "active_clients"]);
  });
});

describe("visibleTopics", () => {
  const topics = [{ key: "business" }, { key: "audit" }, { key: "data" }];

  it("hides the audit log (roles and team activity) in solo mode", () => {
    assert.deepEqual(visibleTopics(topics, true).map((t) => t.key), ["business", "data"]);
  });

  it("keeps every topic once the business has grown", () => {
    assert.deepEqual(visibleTopics(topics, false).map((t) => t.key), ["business", "audit", "data"]);
  });
});
