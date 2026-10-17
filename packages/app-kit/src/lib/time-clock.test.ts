import assert from "node:assert/strict";
import { test } from "node:test";

import { entryHours, formatHours } from "./time-clock.ts";

test("hours are shown as h:mm", () => {
  assert.equal(formatHours(8.5), "8:30");
  assert.equal(formatHours(0), "0:00");
  assert.equal(formatHours(1.999), "2:00");
  assert.equal(formatHours(-0.25), "-0:15");
});

test("an entry counts its length, a running one up to now", () => {
  assert.equal(entryHours("2026-10-12T06:00:00Z", "2026-10-12T14:30:00Z"), 8.5);
  assert.equal(entryHours("2026-10-12T06:00:00Z", null, new Date("2026-10-12T08:00:00Z")), 2);
  assert.equal(entryHours("2026-10-12T06:00:00Z", null, new Date("2026-10-12T05:00:00Z")), 0);
});
