import assert from "node:assert/strict";
import { test } from "node:test";

import { OFFER_PAUSE_DAYS, shouldOfferPush } from "./push-offer-rules.ts";

const DAY = 24 * 60 * 60 * 1000;
const now = Date.parse("2026-10-30T12:00:00Z");

test("offers once to someone who has not decided", () => {
  assert.equal(shouldOfferPush({ available: true, permission: "undetermined", lastAnswerAt: null, now }), true);
});

test("never on the web or without a push project, and never after the phone was answered", () => {
  assert.equal(shouldOfferPush({ available: false, permission: "undetermined", lastAnswerAt: null, now }), false);
  assert.equal(shouldOfferPush({ available: true, permission: "granted", lastAnswerAt: null, now }), false);
  assert.equal(shouldOfferPush({ available: true, permission: "denied", lastAnswerAt: null, now }), false);
});

test("a Not now is respected for two weeks and then the offer returns", () => {
  const answered = now - (OFFER_PAUSE_DAYS - 1) * DAY;
  assert.equal(shouldOfferPush({ available: true, permission: "undetermined", lastAnswerAt: answered, now }), false);
  assert.equal(shouldOfferPush({ available: true, permission: "undetermined", lastAnswerAt: now - OFFER_PAUSE_DAYS * DAY, now }), true);
});
