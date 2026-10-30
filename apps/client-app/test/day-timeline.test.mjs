import { Buffer } from "node:buffer";
import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";

const source = readFileSync(new URL("../src/lib/day-timeline.ts", import.meta.url), "utf8");
const lib = await import(`data:text/javascript;base64,${Buffer.from(stripTypeScriptTypes(source)).toString("base64")}`);

const at = (id, start, end, status = "scheduled") => ({ id, starts_at: `2026-10-25T${start}:00Z`, ends_at: `2026-10-25T${end}:00Z`, status });
const shape = (items) => items.map((i) => (i.kind === "hour" ? `H${i.hour}` : i.kind === "now" ? "NOW" : `${i.session.id}:${i.state}`));

test("groups by hour in the business time zone and places the now marker", () => {
  const items = lib.buildTimeline(
    [at("c", "09:30", "10:30"), at("a", "07:00", "08:00"), at("b", "07:30", "08:30"), at("d", "12:00", "13:00")],
    "UTC",
    Date.parse("2026-10-25T09:00:00Z"),
  );
  assert.deepEqual(shape(items), ["H7", "a:past", "b:past", "NOW", "H9", "c:upcoming", "H12", "d:upcoming"]);
});

test("a running session is live and the marker follows it", () => {
  const items = lib.buildTimeline([at("a", "09:00", "10:00"), at("b", "11:00", "12:00")], "UTC", Date.parse("2026-10-25T09:30:00Z"));
  assert.deepEqual(shape(items), ["H9", "a:live", "NOW", "H11", "b:upcoming"]);
});

test("marker goes last when everything is over, and not at all on other days", () => {
  const items = lib.buildTimeline([at("a", "07:00", "08:00")], "UTC", Date.parse("2026-10-25T20:00:00Z"));
  assert.deepEqual(shape(items), ["H7", "a:past", "NOW"]);
  assert.deepEqual(shape(lib.buildTimeline([at("a", "07:00", "08:00")], "UTC", null)), ["H7", "a:upcoming"]);
});

test("hours follow the time zone", () => {
  const items = lib.buildTimeline([at("a", "17:00", "18:00")], "Asia/Jerusalem", null);
  assert.equal(items[0].hour, 19);
});

test("the now card picks the running session, else the next one, and skips cancelled and finished ones", () => {
  const sessions = [at("a", "07:00", "08:00"), at("b", "09:00", "10:00"), at("c", "09:30", "10:30"), at("x", "11:00", "12:00", "cancelled"), at("d", "13:00", "14:00")];
  const during = lib.focusSession(sessions, Date.parse("2026-10-25T09:40:00Z"));
  assert.deepEqual([during.session.id, during.live], ["b", true]);
  const between = lib.focusSession(sessions, Date.parse("2026-10-25T10:45:00Z"));
  assert.deepEqual([between.session.id, between.live], ["d", false]);
  assert.equal(lib.focusSession(sessions, Date.parse("2026-10-25T15:00:00Z")), null);
  assert.equal(lib.focusSession([], Date.parse("2026-10-25T09:00:00Z")), null);
});
