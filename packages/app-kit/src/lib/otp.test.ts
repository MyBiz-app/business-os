import assert from "node:assert/strict";
import { test } from "node:test";

import { availableChannels, OTP_LENGTH, toE164 } from "./otp.ts";

test("codes are six digits", () => {
  assert.equal(OTP_LENGTH, 6);
});

test("email is always offered; phone channels need the project's SMS provider", () => {
  assert.deepEqual(availableChannels(null, true), ["email"]);
  assert.deepEqual(availableChannels({ external: { phone: false } }, true), ["email"]);
  assert.deepEqual(availableChannels({ external: { phone: true } }, false), ["email", "sms"]);
  assert.deepEqual(availableChannels({ external: { phone: true } }, true), ["email", "sms", "whatsapp"]);
});

test("phone numbers become E.164", () => {
  assert.equal(toE164("050-123 4567"), "+972501234567");
  assert.equal(toE164("+1 (415) 212-7777"), "+14152127777");
  assert.equal(toE164("00972501234567"), "+972501234567");
  assert.equal(toE164("501234567"), null);
  assert.equal(toE164("123"), null);
  assert.equal(toE164(""), null);
});
