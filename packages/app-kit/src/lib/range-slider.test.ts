import assert from "node:assert/strict";
import { test } from "node:test";

import { fractionOf, moveHandle, valueAt } from "./range-slider.ts";

test("a position snaps to the step and stays inside the track", () => {
  assert.equal(valueAt(0.5, 0, 1440, 30), 720);
  assert.equal(valueAt(0.5021, 0, 1440, 30), 720);
  assert.equal(valueAt(-1, 0, 1440, 30), 0);
  assert.equal(valueAt(2, 0, 1440, 30), 1440);
});

test("a value maps back to its place along the track", () => {
  assert.equal(fractionOf(720, 0, 1440), 0.5);
  assert.equal(fractionOf(5000, 0, 1440), 1);
  assert.equal(fractionOf(5, 10, 10), 0);
});

test("the handles never cross and keep the gap", () => {
  const range = { from: 540, to: 720 };
  assert.deepEqual(moveHandle(range, "from", 900, 0, 1440, 30), { from: 690, to: 720 });
  assert.deepEqual(moveHandle(range, "to", 0, 0, 1440, 30), { from: 540, to: 570 });
  assert.deepEqual(moveHandle(range, "from", -60, 0, 1440, 30), { from: 0, to: 720 });
  assert.deepEqual(moveHandle(range, "to", 2000, 0, 1440, 30), { from: 540, to: 1440 });
});
