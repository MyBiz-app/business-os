import assert from "node:assert/strict";
import { test } from "node:test";

import { zonedToIso } from "./zoned.ts";

test("local wall-clock times become the right instants", () => {
  assert.equal(zonedToIso("2026-01-15", "09:00", "Asia/Jerusalem"), "2026-01-15T07:00:00.000Z");
  assert.equal(zonedToIso("2026-07-15", "09:00", "Asia/Jerusalem"), "2026-07-15T06:00:00.000Z");
  assert.equal(zonedToIso("2026-07-15", "09:30", "UTC"), "2026-07-15T09:30:00.000Z");
  assert.equal(zonedToIso("2026-03-08", "12:00", "America/New_York"), "2026-03-08T16:00:00.000Z");
});
