import assert from "node:assert/strict";
import { test } from "node:test";

import { chunkRange, rangeFor, shiftView, stepDay } from "./calendar-range.ts";

test("week range starts on Sunday", () => {
  assert.deepEqual(rangeFor("week", "2026-10-14"), { start: "2026-10-11", days: 7 });
});

test("month range is whole weeks", () => {
  const r = rangeFor("month", "2026-10-14");
  assert.equal(r.days % 7, 0);
  assert.equal(r.start, "2026-09-27");
});

test("chunks respect the API limit", () => {
  const parts = chunkRange("2026-09-27", 35);
  assert.deepEqual(parts.map((p) => p.days), [14, 14, 7]);
  assert.equal(parts[1].start, "2026-10-11");
});

test("steps and view shifts", () => {
  assert.equal(stepDay("day", "2026-10-14", -1), "2026-10-13");
  assert.equal(stepDay("week", "2026-10-14", 1), "2026-10-21");
  assert.equal(stepDay("month", "2026-01-31", 1), "2026-02-28");
  assert.equal(shiftView("day", "up"), "week");
  assert.equal(shiftView("month", "up"), "month");
  assert.equal(shiftView("week", "down"), "day");
});
