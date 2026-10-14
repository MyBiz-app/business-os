import assert from "node:assert/strict";
import { test } from "node:test";

import { normalizeStatus, STATUS_MAX_LENGTH, statusChanged } from "./profile-status.ts";

test("a status is trimmed and cut to the limit", () => {
  assert.equal(normalizeStatus("  Training for a 10K  "), "Training for a 10K");
  assert.equal(normalizeStatus("x".repeat(100))?.length, STATUS_MAX_LENGTH);
});

test("a blank status means no status", () => {
  assert.equal(normalizeStatus("   "), null);
});

test("changes are detected against the saved status", () => {
  assert.equal(statusChanged(" hi ", "hi"), false);
  assert.equal(statusChanged("", null), false);
  assert.equal(statusChanged("hi", null), true);
  assert.equal(statusChanged("", "hi"), true);
});
