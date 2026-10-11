import assert from "node:assert/strict";
import { test } from "node:test";

import { branchLimit, rangeOfCadence, stepWindow, windowOf } from "./shift-window.ts";

test("a rhythm opens the matching window", () => {
  assert.equal(rangeOfCadence("daily"), "day");
  assert.equal(rangeOfCadence("weekly"), "week");
  assert.equal(rangeOfCadence("monthly"), "month");
  assert.equal(rangeOfCadence(undefined), "week");
});

test("windows cover the day, the week, the month or N days", () => {
  assert.deepEqual(windowOf("day", "2026-10-14"), { start: "2026-10-14", days: 1 });
  assert.deepEqual(windowOf("week", "2026-10-14"), { start: "2026-10-11", days: 7 });
  assert.deepEqual(windowOf("month", "2026-10-14"), { start: "2026-10-01", days: 31 });
  assert.deepEqual(windowOf("month", "2028-02-10"), { start: "2028-02-01", days: 29 });
  assert.deepEqual(windowOf("custom", "2026-10-14", 10), { start: "2026-10-14", days: 10 });
});

test("stepping moves by the window, months by calendar month", () => {
  assert.equal(stepWindow("day", windowOf("day", "2026-10-14"), 1), "2026-10-15");
  assert.equal(stepWindow("week", windowOf("week", "2026-10-14"), -1), "2026-10-04");
  assert.equal(stepWindow("month", windowOf("month", "2026-12-20"), 1), "2027-01-01");
  assert.equal(stepWindow("month", windowOf("month", "2026-01-20"), -1), "2025-12-01");
  assert.equal(stepWindow("custom", windowOf("custom", "2026-10-14", 10), 1), "2026-10-24");
});

test("fewer branches fit side by side as the window grows", () => {
  assert.ok(branchLimit("day") > branchLimit("week"));
  assert.equal(branchLimit("week"), 3);
  assert.equal(branchLimit("month"), 1);
});
