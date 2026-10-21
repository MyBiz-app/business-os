import assert from "node:assert/strict";
import { test } from "node:test";

import { accountStatusItems, type AccountStatusInput, cardDismissed, riskPromptUrl, withoutRiskPrompt } from "./account-status.ts";

const NOW = Date.parse("2026-10-21T10:00:00Z");
const owner: AccountStatusInput = {
  platform: false,
  roles: ["owner"],
  mfaEnforced: true,
  hasAuthenticator: false,
  riskAcknowledged: false,
  snoozedUntil: null,
  addressComplete: true,
  addressSkipped: false,
  now: NOW,
};

test("an owner without two-step sign-in is reminded until they turn it on, snooze or decline it", () => {
  assert.deepEqual(accountStatusItems(owner), ["mfa"]);
  assert.deepEqual(accountStatusItems({ ...owner, roles: ["manager"] }), ["mfa"]);
  assert.deepEqual(accountStatusItems({ ...owner, hasAuthenticator: true }), []);
  assert.deepEqual(accountStatusItems({ ...owner, riskAcknowledged: true }), []);
  assert.deepEqual(accountStatusItems({ ...owner, snoozedUntil: "2026-10-28T10:00:00Z" }), []);
  // A week later the reminder is back.
  assert.deepEqual(accountStatusItems({ ...owner, snoozedUntil: "2026-10-21T09:59:00Z" }), ["mfa"]);
  assert.deepEqual(accountStatusItems({ ...owner, mfaEnforced: false }), []);
});

test("staff are not asked about two-step sign-in, the MyBiz team always is", () => {
  assert.deepEqual(accountStatusItems({ ...owner, roles: ["staff"] }), []);
  const team = { ...owner, platform: true, roles: [], riskAcknowledged: true, snoozedUntil: "2026-10-28T10:00:00Z" };
  assert.deepEqual(accountStatusItems(team), ["mfa_required"]);
});

test("the home address is asked of team members until filled in or skipped", () => {
  const missing = { ...owner, hasAuthenticator: true, addressComplete: false, roles: ["staff"] };
  assert.deepEqual(accountStatusItems(missing), ["address"]);
  assert.deepEqual(accountStatusItems({ ...missing, addressSkipped: true }), []);
  assert.deepEqual(accountStatusItems({ ...missing, roles: [] }), []);
  assert.deepEqual(accountStatusItems({ ...owner, addressComplete: false }), ["mfa", "address"]);
});

test("a closed card comes back only for a new item", () => {
  assert.equal(cardDismissed(["mfa", "address"], undefined), false);
  assert.equal(cardDismissed(["mfa", "address"], "address.mfa"), true);
  assert.equal(cardDismissed(["mfa"], "address.mfa"), true);
  assert.equal(cardDismissed(["mfa", "address"], "address"), false);
});

test("a refused sensitive action opens the warning on the same page, once", () => {
  assert.equal(riskPromptUrl("/settings/team", ""), "/settings/team?mfa=ack");
  assert.equal(riskPromptUrl("/clients", "?status=active"), "/clients?status=active&mfa=ack");
  assert.equal(riskPromptUrl("/clients", "?mfa=ack"), null);
  assert.equal(withoutRiskPrompt("/clients", "?status=active&mfa=ack"), "/clients?status=active");
  assert.equal(withoutRiskPrompt("/clients", "?mfa=ack"), "/clients");
});
