import { Buffer } from "node:buffer";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import { test } from "node:test";

const source = readFileSync(new URL("../src/lib/class-filters.ts", import.meta.url), "utf8");
const lib = await import(`data:text/javascript;base64,${Buffer.from(stripTypeScriptTypes(source)).toString("base64")}`);

const session = (service, instructor) => ({ service: { id: service, name: service.toUpperCase() }, instructor });
const dana = { id: "i1", name: "Dana" };
const sessions = [session("yoga", dana), session("pilates", { id: "i2", name: "Noa" }), session("yoga", null), session("yoga", dana)];

test("filter options list each instructor and class type once", () => {
  const { instructors, services } = lib.filterOptions(sessions);
  assert.deepEqual(instructors, [{ id: "i1", name: "Dana" }, { id: "i2", name: "Noa" }]);
  assert.deepEqual(services.map((s) => s.id), ["yoga", "pilates"]);
});

test("filters combine; none keeps everything", () => {
  assert.equal(lib.applyFilters(sessions, lib.NO_FILTERS).length, 4);
  assert.equal(lib.applyFilters(sessions, { instructorId: "i1", serviceId: null }).length, 2);
  assert.equal(lib.applyFilters(sessions, { instructorId: "i2", serviceId: "yoga" }).length, 0);
});

test("fill ratio is clamped", () => {
  assert.equal(lib.fillRatio(8, 2), 0.75);
  assert.equal(lib.fillRatio(0, 0), 0);
  assert.equal(lib.fillRatio(5, -1), 1);
});

test("a release in the past is not announced", () => {
  const now = Date.parse("2026-10-14T12:00:00Z");
  assert.equal(lib.upcomingRelease(null, now), null);
  assert.equal(lib.upcomingRelease("2026-10-14T11:00:00Z", now), null);
  assert.equal(lib.upcomingRelease("2026-10-15T17:00:00Z", now)?.toISOString(), "2026-10-15T17:00:00.000Z");
});
