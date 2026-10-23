import assert from "node:assert/strict";
import { test } from "node:test";

import { circleInitials, neighbour, rebookTarget, swipeStep, waitingCounts } from "./all-mine.ts";

test("a swipe moves to the next or previous business and stops at the ends", () => {
  const ids = ["a", "b", "c"];
  assert.equal(neighbour(ids, "b", 1), "c");
  assert.equal(neighbour(ids, "b", -1), "a");
  assert.equal(neighbour(ids, "c", 1), null);
  assert.equal(neighbour(ids, "a", -1), null);
  assert.equal(neighbour(ids, "gone", 1), null);
  assert.equal(neighbour(ids, null, 1), null);
});

test("only a clear sideways drag swipes, and right-to-left flips it", () => {
  assert.equal(swipeStep(-120, 10, false), 1);
  assert.equal(swipeStep(120, 10, false), -1);
  assert.equal(swipeStep(120, 10, true), 1);
  assert.equal(swipeStep(-120, 10, true), -1);
  assert.equal(swipeStep(-30, 0, false), null); // too short
  assert.equal(swipeStep(-100, 90, false), null); // a scroll, not a swipe
});

test("waiting items are counted per business", () => {
  const counts = waitingCounts([
    { business_id: "a", kind: "health" },
    { business_id: "a", kind: "document" },
    { business_id: "b", kind: "invite" },
  ]);
  assert.deepEqual(counts, { a: 2, b: 1 });
});

test("initials use the first letter of the first two words", () => {
  assert.equal(circleInitials("Blade Barbers"), "BB");
  assert.equal(circleInitials("אדיר פיטנס"), "אפ");
  assert.equal(circleInitials("Merhav"), "M");
  assert.equal(circleInitials("Sharon Tennis Club"), "ST");
});

test("book again opens the screen the thing was booked on", () => {
  assert.equal(rebookTarget("class"), "/schedule");
  assert.equal(rebookTarget("appointment"), "/appointment");
  assert.equal(rebookTarget("resource"), "/court");
});
