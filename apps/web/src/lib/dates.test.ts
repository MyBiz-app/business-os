import assert from "node:assert/strict";
import { test } from "node:test";

import { addDays, dayOf, isDay, todayIn, toApiWeekday, weekStart } from "./dates.ts";

test("today depends on the business time zone, not the server's", () => {
  const instant = new Date("2026-10-11T22:30:00Z"); // Sunday night in UTC, Monday in Israel
  assert.equal(todayIn("Asia/Jerusalem", instant), "2026-10-12");
  assert.equal(todayIn("America/New_York", instant), "2026-10-11");
});

test("week starts on Sunday and spans month and year boundaries", () => {
  assert.equal(weekStart("2026-10-14"), "2026-10-11");
  assert.equal(weekStart("2026-10-11"), "2026-10-11");
  assert.equal(weekStart("2027-01-01"), "2026-12-27");
  assert.equal(addDays("2026-12-31", 1), "2027-01-01");
});

test("local day of an instant", () => {
  assert.equal(dayOf("2026-10-11T22:30:00Z", "Asia/Jerusalem"), "2026-10-12");
});

test("validates day strings and converts weekdays", () => {
  assert.ok(isDay("2026-10-11"));
  assert.ok(!isDay("2026-13-40"));
  assert.ok(!isDay("next week"));
  assert.equal(toApiWeekday(0), 6); // Sunday
  assert.equal(toApiWeekday(1), 0); // Monday
});
