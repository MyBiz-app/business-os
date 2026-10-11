import assert from "node:assert/strict";
import { test } from "node:test";

import { timeOffProblem } from "./time-off.ts";

const today = "2026-10-11";

test("accepts a period that has not ended", () => {
  assert.equal(timeOffProblem("2026-10-12", "2026-10-14", today), null);
  assert.equal(timeOffProblem("2026-10-09", "2026-10-11", today), null);
});

test("rejects malformed, reversed, past and over-long periods", () => {
  assert.equal(timeOffProblem("12/10/2026", "2026-10-14", today), "invalid_date");
  assert.equal(timeOffProblem("2026-10-14", "2026-10-12", today), "ends_before_start");
  assert.equal(timeOffProblem("2026-10-01", "2026-10-02", today), "in_the_past");
  assert.equal(timeOffProblem("2026-10-12", "2028-01-01", today), "too_long");
});
