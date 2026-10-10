import assert from "node:assert/strict";
import { test } from "node:test";

import { branchColor, capLanes, coverage, layOut, minutesIn, visibleHours } from "./calendar.ts";

test("minutes since local midnight follow the time zone", () => {
  assert.equal(minutesIn("2026-10-10T06:30:00Z", "Asia/Jerusalem"), 9 * 60 + 30);
  assert.equal(minutesIn("2026-10-10T06:30:00Z", "UTC"), 6 * 60 + 30);
});

test("overlapping events share the width; separate ones keep it", () => {
  const placed = layOut([
    { id: "a", start: 540, end: 600 },
    { id: "b", start: 570, end: 630 },
    { id: "c", start: 600, end: 660 },
    { id: "d", start: 700, end: 760 },
  ]);
  const by = Object.fromEntries(placed.map((p) => [p.id, p]));
  assert.deepEqual([by.a.lane, by.b.lane, by.c.lane], [0, 1, 0]);
  assert.deepEqual([by.a.lanes, by.b.lanes, by.c.lanes], [2, 2, 2]);
  assert.deepEqual([by.d.lane, by.d.lanes], [0, 1]);
});

test("the grid covers working hours and every event", () => {
  assert.deepEqual(visibleHours([]), { from: 480, to: 1200 });
  assert.deepEqual(
    visibleHours([
      { start: 390, end: 450 },
      { start: 1290, end: 1330 },
    ]),
    { from: 360, to: 1380 },
  );
});

test("branch colors are stable and wrap around", () => {
  assert.equal(branchColor(0), branchColor(9));
  assert.notEqual(branchColor(0), branchColor(1));
});

test("a crowded cluster keeps its first lanes and folds the rest into one block", () => {
  const events = ["a", "b", "c", "d", "e"].map((id, i) => ({
    id,
    start: 600 + i * 10,
    end: 700,
  }));
  const { shown, more } = capLanes(layOut([...events, { id: "late", start: 800, end: 860 }]), 3);
  assert.deepEqual(
    shown.map((e) => [e.id, e.lane, e.lanes]),
    [
      ["a", 0, 3],
      ["b", 1, 3],
      ["late", 0, 1],
    ],
  );
  assert.deepEqual(more, [{ id: "more-0", start: 620, end: 700, lane: 2, lanes: 3, count: 3 }]);
});

test("coverage counts who is on at each stretch", () => {
  const segments = coverage([
    { start: 540, end: 1020 },
    { start: 540, end: 780 },
    { start: 840, end: 1020 },
  ]);
  assert.deepEqual(segments, [
    { start: 540, end: 780, count: 2 },
    { start: 780, end: 840, count: 1 },
    { start: 840, end: 1020, count: 2 },
  ]);
});
