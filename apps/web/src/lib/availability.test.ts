import assert from "node:assert/strict";
import { test } from "node:test";

import { mondayWeekday, outsideAvailability } from "./availability.ts";

// 2024-01-01 was a Monday.
test("weekdays count from Monday", () => {
  assert.equal(mondayWeekday("2024-01-01"), 0);
  assert.equal(mondayWeekday("2024-01-07"), 6);
});

test("nothing said is never outside", () => {
  assert.equal(outsideAvailability(null, "2024-01-01", "09:00", "17:00"), false);
  assert.equal(outsideAvailability([], "2024-01-01", "09:00", "17:00"), false);
});

test("a shift fits within one window of its day", () => {
  const week = [{ weekday: 0, starts: "08:00:00", ends: "12:00:00" }];
  assert.equal(outsideAvailability(week, "2024-01-01", "08:00", "12:00"), false);
  assert.equal(outsideAvailability(week, "2024-01-01", "09:00", "13:00"), true);
  assert.equal(outsideAvailability(week, "2024-01-02", "08:00", "12:00"), true);
});

test("past midnight needs the evening and the next morning", () => {
  const evening = { weekday: 6, starts: "20:00", ends: "23:59" };
  assert.equal(outsideAvailability([evening], "2024-01-07", "22:00", "00:00"), false);
  assert.equal(outsideAvailability([evening], "2024-01-07", "22:00", "02:00"), true);
  assert.equal(outsideAvailability([evening, { weekday: 0, starts: "00:00", ends: "03:00" }], "2024-01-07", "22:00", "02:00"), false);
});
