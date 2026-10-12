import assert from "node:assert/strict";
import { test } from "node:test";

import { availabilityProblem, normalizeTime, weekdayOrder } from "./availability.ts";

test("times are read leniently", () => {
  assert.equal(normalizeTime(" 8:00 "), "08:00");
  assert.equal(normalizeTime("16:30:00"), "16:30");
});

test("a week is checked like the API checks it", () => {
  assert.equal(availabilityProblem([]), null);
  assert.equal(availabilityProblem([{ weekday: 0, starts: "8:00", ends: "12:00" }]), null);
  assert.equal(availabilityProblem([{ weekday: 0, starts: "8", ends: "12:00" }]), "invalid_time");
  assert.equal(availabilityProblem([{ weekday: 0, starts: "08:00", ends: "24:00" }]), "invalid_time");
  assert.equal(availabilityProblem([{ weekday: 0, starts: "12:00", ends: "08:00" }]), "ends_before_start");
  assert.equal(
    availabilityProblem([
      { weekday: 0, starts: "08:00", ends: "12:00" },
      { weekday: 0, starts: "11:00", ends: "14:00" },
    ]),
    "overlap",
  );
  assert.equal(
    availabilityProblem([
      { weekday: 0, starts: "08:00", ends: "12:00" },
      { weekday: 1, starts: "11:00", ends: "14:00" },
    ]),
    null,
  );
});

test("the week can start on Sunday", () => {
  assert.deepEqual(weekdayOrder(true).slice(0, 2), [6, 0]);
  assert.deepEqual(weekdayOrder(false).slice(0, 2), [0, 1]);
});
