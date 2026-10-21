import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { LOCKED_GRACE_DAYS, lockedMenuMode } from "./nav-capabilities.ts";

const DAY = 24 * 60 * 60 * 1000;
const NOW = Date.parse("2026-11-30T12:00:00Z");

describe("lockedMenuMode", () => {
  it("keeps separate grey items during the first 30 days", () => {
    assert.equal(lockedMenuMode(new Date(NOW - (LOCKED_GRACE_DAYS - 1) * DAY).toISOString(), NOW), "items");
  });
  it("folds into one item from day 30", () => {
    assert.equal(lockedMenuMode(new Date(NOW - LOCKED_GRACE_DAYS * DAY).toISOString(), NOW), "folded");
  });
  it("keeps items when the date is missing or unreadable", () => {
    assert.equal(lockedMenuMode(null, NOW), "items");
    assert.equal(lockedMenuMode("not a date", NOW), "items");
  });
});
