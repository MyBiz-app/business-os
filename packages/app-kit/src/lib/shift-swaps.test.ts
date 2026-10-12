import assert from "node:assert/strict";
import { test } from "node:test";

import { canOfferSwap } from "./shift-swaps.ts";

const now = new Date("2026-10-11T10:00:00Z");
const shift = { id: "a", starts_at: "2026-10-12T09:00:00Z", published: true };

test("offers a published upcoming shift with no open swap", () => {
  assert.equal(canOfferSwap(shift, [], now), true);
  assert.equal(canOfferSwap(shift, [{ shift_id: "a", status: "refused" }], now), true);
});

test("blocks drafts, started shifts and shifts with an open swap", () => {
  assert.equal(canOfferSwap({ ...shift, published: false }, [], now), false);
  assert.equal(canOfferSwap({ ...shift, starts_at: "2026-10-11T09:00:00Z" }, [], now), false);
  assert.equal(canOfferSwap(shift, [{ shift_id: "a", status: "pending_manager" }], now), false);
});
