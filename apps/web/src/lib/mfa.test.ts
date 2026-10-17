import assert from "node:assert/strict";
import { test } from "node:test";

import { deviceLabel, INACTIVITY_LIMIT_MS, isCode, isInactive, isMfaExempt, needsCodeStep } from "./mfa.ts";

test("a session is idle only after the limit", () => {
  const now = 1_000_000_000_000;
  assert.equal(isInactive(undefined, now), false);
  assert.equal(isInactive("garbage", now), false);
  assert.equal(isInactive(String(now - INACTIVITY_LIMIT_MS + 1000), now), false);
  assert.equal(isInactive(String(now - INACTIVITY_LIMIT_MS - 1000), now), true);
});

test("a code step is needed only for someone with an authenticator who has not used it", () => {
  assert.equal(needsCodeStep("aal1", "aal2"), true);
  assert.equal(needsCodeStep("aal2", "aal2"), false);
  assert.equal(needsCodeStep("aal1", "aal1"), false);
  assert.equal(needsCodeStep(undefined, undefined), false);
});

test("a code is six digits", () => {
  assert.equal(isCode("123456"), true);
  assert.equal(isCode("12345"), false);
  assert.equal(isCode("12345a"), false);
  assert.equal(isCode("1234567"), false);
});

test("a device is described by browser and system", () => {
  assert.equal(
    deviceLabel("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Chrome on Windows",
  );
  assert.equal(
    deviceLabel("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"),
    "Safari on iOS",
  );
  assert.equal(deviceLabel(""), "Browser");
});

test("only listed demo emails skip the code step", () => {
  assert.equal(isMfaExempt("Demo@example.com", "a@x.com, demo@example.com"), true);
  assert.equal(isMfaExempt("other@example.com", "demo@example.com"), false);
  assert.equal(isMfaExempt("demo@example.com", ""), false);
  assert.equal(isMfaExempt(undefined, "demo@example.com"), false);
});
