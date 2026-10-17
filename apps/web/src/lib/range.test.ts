import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { MAX_RANGE_DAYS, rangeShortcuts, resolveRange } from "./range.ts";

const today = "2026-10-17";
const options = { presets: [7, 30, 90], fallback: 30 };

describe("resolveRange", () => {
  it("defaults to the last 30 completed days", () => {
    assert.deepEqual(resolveRange({}, today, options), { key: "30", start: "2026-09-17", end: "2026-10-16", days: 30 });
  });

  it("takes a preset from the link and can include today", () => {
    assert.deepEqual(resolveRange({ period: "7" }, today, { ...options, includeToday: true }), { key: "7", start: "2026-10-11", end: "2026-10-17", days: 7 });
  });

  it("takes a free range, today included", () => {
    assert.deepEqual(resolveRange({ from: "2026-10-01", to: "2026-10-17" }, today, options), { key: "custom", start: "2026-10-01", end: "2026-10-17", days: 17 });
  });

  it("ignores a range that is backwards, in the future, too long or not a date", () => {
    for (const query of [
      { from: "2026-10-10", to: "2026-10-01" },
      { from: "2026-10-01", to: "2026-10-18" },
      { from: "2025-01-01", to: "2026-10-17" },
      { from: "soon", to: "2026-10-17" },
      { from: "2026-10-01" },
    ]) {
      assert.equal(resolveRange(query, today, options).key, "30");
    }
    assert.ok(MAX_RANGE_DAYS >= 366);
  });
});

describe("rangeShortcuts", () => {
  it("offers this month, last month and the year so far", () => {
    assert.deepEqual(
      rangeShortcuts(today).map(({ key, from, to }) => [key, from, to]),
      [
        ["thisMonth", "2026-10-01", "2026-10-17"],
        ["lastMonth", "2026-09-01", "2026-09-30"],
        ["yearToDate", "2026-01-01", "2026-10-17"],
      ],
    );
  });
});
