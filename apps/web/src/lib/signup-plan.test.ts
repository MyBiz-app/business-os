import assert from "node:assert/strict";
import { test } from "node:test";

import { decodePlan, encodePlan, priceLines, type SignupPlan, withLocations } from "./signup-plan.ts";

const catalog = {
  core: [
    { up_to_clients: 100, price: 9900 },
    { up_to_clients: 300, price: 14900 },
    { up_to_clients: 1000, price: 24900 },
    { up_to_clients: null, price: 24900 },
  ],
  modules: [
    { key: "client_app", price: 4900 },
    { key: "ai_basic", price: 4900 },
    { key: "extra_location", price: 2900 },
  ],
};

const plan: SignupPlan = {
  vertical: "beauty",
  name: "סלון שירה",
  clients: 300,
  staff: 3,
  locations: 3,
  currency: "ILS",
  modules: { client_app: 1, extra_location: 2 },
};

test("a plan survives the round trip through the URL, Hebrew included", () => {
  const encoded = encodePlan(plan);
  assert.match(encoded, /^[A-Za-z0-9_-]+$/);
  assert.deepEqual(decodePlan(encoded), plan);
});

test("anything that is not a valid plan is rejected", () => {
  assert.equal(decodePlan(undefined), null);
  assert.equal(decodePlan("not base64 json"), null);
  assert.equal(decodePlan(encodePlan({ ...plan, vertical: "bakery" as "beauty" })), null);
  assert.equal(decodePlan(encodePlan({ ...plan, name: "  " })), null);
  assert.equal(decodePlan(encodePlan({ ...plan, modules: { rocket: 1 } as never })), null);
  assert.equal(decodePlan(encodePlan({ ...plan, modules: { crm: 0 } })), null);
});

test("prices: the core by size, then modules by quantity", () => {
  const { lines, total } = priceLines(catalog, plan);
  assert.deepEqual(lines, [
    { key: "core", quantity: 1, amount: 14900 },
    { key: "client_app", quantity: 1, amount: 4900 },
    { key: "extra_location", quantity: 2, amount: 5800 },
  ]);
  assert.equal(total, 25600);
  assert.equal(priceLines(catalog, { clients: 5000, modules: {} }).total, 24900);
});

test("every location after the first is an extra location", () => {
  assert.deepEqual(withLocations({ crm: 1 }, 1), { crm: 1 });
  assert.deepEqual(withLocations({ crm: 1, extra_location: 4 }, 2), { crm: 1, extra_location: 1 });
});
