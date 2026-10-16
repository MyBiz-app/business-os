import { Buffer } from "node:buffer";
import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";

const source = readFileSync(new URL("../src/lib/availability.ts", import.meta.url), "utf8");
const lib = await import(`data:text/javascript;base64,${Buffer.from(stripTypeScriptTypes(source)).toString("base64")}`);

const court = (room, iso) => ({ room_id: room, room_name: `Court ${room}`, starts_at: iso });

test("clockOf uses the business time zone", () => {
  assert.equal(lib.clockOf("2026-10-16T17:00:00Z", "Asia/Jerusalem"), "20:00");
});

test("courtGrid builds hours as columns and courts as rows", () => {
  const grid = lib.courtGrid(
    [court("1", "2026-10-16T17:00:00Z"), court("2", "2026-10-16T17:00:00Z"), court("1", "2026-10-16T18:00:00Z")],
    "UTC",
  );
  assert.deepEqual(grid.hours, ["17:00", "18:00"]);
  assert.deepEqual(grid.courts.map((c) => [c.name, Object.keys(c.cells)]), [["Court 1", ["17:00", "18:00"]], ["Court 2", ["17:00"]]]);
});

test("staffRows groups by person with times in order", () => {
  const rows = lib.staffRows([
    { staff_user_id: "b", staff_name: "Dana", starts_at: "2026-10-16T12:00:00Z" },
    { staff_user_id: "a", staff_name: "Avi", starts_at: "2026-10-16T11:00:00Z" },
    { staff_user_id: "b", staff_name: "Dana", starts_at: "2026-10-16T09:00:00Z" },
  ]);
  assert.deepEqual(rows.map((r) => [r.name, r.slots.length, r.slots[0].starts_at]), [["Avi", 1, "2026-10-16T11:00:00Z"], ["Dana", 2, "2026-10-16T09:00:00Z"]]);
});
