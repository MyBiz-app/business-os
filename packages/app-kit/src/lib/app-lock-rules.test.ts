import assert from "node:assert/strict";
import { test } from "node:test";

import { LOCK_AFTER_MS, shouldLock } from "./app-lock-rules.ts";

test("never locks when the lock is off or the app was not backgrounded", () => {
  assert.equal(shouldLock(false, 0, LOCK_AFTER_MS * 2), false);
  assert.equal(shouldLock(true, null, 1_000_000), false);
});

test("locks only after the grace period", () => {
  assert.equal(shouldLock(true, 1_000, 1_000 + LOCK_AFTER_MS - 1), false);
  assert.equal(shouldLock(true, 1_000, 1_000 + LOCK_AFTER_MS), true);
});
