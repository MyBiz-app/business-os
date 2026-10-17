import assert from "node:assert/strict";
import { test } from "node:test";

import { isSessionStale, needsCodeStep, SESSION_MAX_IDLE_MS, shouldRefreshStamp } from "./session-rules.ts";

test("the app signs out after thirty days unopened", () => {
  const now = 2_000_000_000_000;
  assert.equal(isSessionStale(null, now), false);
  assert.equal(isSessionStale(now - SESSION_MAX_IDLE_MS + 1000, now), false);
  assert.equal(isSessionStale(now - SESSION_MAX_IDLE_MS - 1000, now), true);
});

test("the stamp is rewritten at most hourly", () => {
  const now = 2_000_000_000_000;
  assert.equal(shouldRefreshStamp(null, now), true);
  assert.equal(shouldRefreshStamp(now - 60_000, now), false);
  assert.equal(shouldRefreshStamp(now - 2 * 60 * 60 * 1000, now), true);
});

test("a code step is needed only for someone with an authenticator who has not used it", () => {
  assert.equal(needsCodeStep("aal1", "aal2"), true);
  assert.equal(needsCodeStep("aal2", "aal2"), false);
  assert.equal(needsCodeStep("aal1", "aal1"), false);
});
