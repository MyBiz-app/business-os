import assert from "node:assert/strict";
import { test } from "node:test";

import { initialOf, LOCK_AFTER_MS, parseLockTimeout, shouldLock, shouldOfferLock } from "./app-lock-rules.ts";

test("never locks when the lock is off or the app was not backgrounded", () => {
  assert.equal(shouldLock(false, 0, LOCK_AFTER_MS * 2), false);
  assert.equal(shouldLock(true, null, 1_000_000), false);
});

test("locks only after the grace period", () => {
  assert.equal(shouldLock(true, 1_000, 1_000 + LOCK_AFTER_MS - 1), false);
  assert.equal(shouldLock(true, 1_000, 1_000 + LOCK_AFTER_MS), true);
});

test("the timeout option changes the grace period", () => {
  assert.equal(shouldLock(true, 1_000, 1_000, "immediate"), true);
  assert.equal(shouldLock(true, 1_000, 1_000 + 299_999, "5m"), false);
  assert.equal(shouldLock(true, 1_000, 1_000 + 300_000, "5m"), true);
});

test("an unknown stored timeout falls back to 30 seconds", () => {
  assert.equal(parseLockTimeout("5m"), "5m");
  assert.equal(parseLockTimeout("bogus"), "30s");
  assert.equal(parseLockTimeout(null), "30s");
});

test("the Face ID offer shows once, only when supported and undecided", () => {
  assert.equal(shouldOfferLock(true, false, false), true);
  assert.equal(shouldOfferLock(false, false, false), false);
  assert.equal(shouldOfferLock(true, true, false), false);
  assert.equal(shouldOfferLock(true, false, true), false);
});

test("the avatar initial is upper case, with a fallback", () => {
  assert.equal(initialOf(" adir@x.com"), "A");
  assert.equal(initialOf(""), "?");
  assert.equal(initialOf(null), "?");
});
