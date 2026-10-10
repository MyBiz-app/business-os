import assert from "node:assert/strict";
import { test } from "node:test";

import { endInputValue, minuteToTime, timeToMinute } from "./coverage.ts";

test("minutes and times convert both ways", () => {
  assert.equal(minuteToTime(450), "07:30");
  assert.equal(minuteToTime(1440), "24:00");
  assert.equal(timeToMinute("07:30"), 450);
});

test("an end of 00:00 is the end of the day", () => {
  assert.equal(timeToMinute("00:00", true), 1440);
  assert.equal(timeToMinute("00:00"), 0);
  assert.equal(endInputValue(1440), "00:00");
  assert.equal(endInputValue(900), "15:00");
});
