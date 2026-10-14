import { Buffer } from "node:buffer";
import assert from "node:assert/strict";
import { test } from "node:test";

// Node can't import .ts directly here, so exercise the logic through a stripped copy.
import { readFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";

const source = readFileSync(new URL("../src/lib/court-search.ts", import.meta.url), "utf8");
const js = stripTypeScriptTypes(source);
const lib = await import(`data:text/javascript;base64,${Buffer.from(js).toString("base64")}`);

test("rental lengths prefer 1h, 1.5h and 2h", () => {
  assert.deepEqual(lib.rentalLengths({ min_minutes: 60, max_minutes: 180, step_minutes: 30 }), [60, 90, 120]);
  assert.deepEqual(lib.rentalLengths({ min_minutes: 60, max_minutes: 120, step_minutes: 60 }), [60, 120]);
  assert.deepEqual(lib.rentalLengths({ min_minutes: 45, max_minutes: 90, step_minutes: 15 }), [60, 90]);
  assert.deepEqual(lib.rentalLengths({ min_minutes: 45, max_minutes: 45, step_minutes: 15 }), [45]);
});

test("default time is the next full hour, within the range", () => {
  assert.equal(lib.defaultTime("UTC", new Date("2026-10-14T15:20:00Z")), "16:00");
  assert.equal(lib.defaultTime("UTC", new Date("2026-10-14T02:00:00Z")), "06:00");
  assert.equal(lib.defaultTime("UTC", new Date("2026-10-14T23:30:00Z")), "23:00");
});

test("offsets split into hours and minutes with direction", () => {
  assert.deepEqual(lib.splitOffset(-90), { later: false, hours: 1, minutes: 30 });
  assert.deepEqual(lib.splitOffset(30), { later: true, hours: 0, minutes: 30 });
});

test("slots group by court", () => {
  const groups = lib.groupByCourt([
    { room_id: "a", room_name: "A", t: 1 },
    { room_id: "b", room_name: "B", t: 2 },
    { room_id: "a", room_name: "A", t: 3 },
  ]);
  assert.equal(groups.length, 2);
  assert.equal(groups[0].slots.length, 2);
});
