import assert from "node:assert/strict";
import { test } from "node:test";

import { chooseTier, decodePlan, encodePlan, priceLines, type SignupPlan, tierOf, withLocations, withoutOrphans } from "./signup-plan.ts";

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
    { key: "client_app_branded", price: 9900, requires_all: ["client_app"] },
    { key: "whatsapp", price: 2900 },
    { key: "whatsapp_ai", price: 5900, requires_all: ["whatsapp"], requires_any: ["ai_basic", "ai_pro"] },
    { key: "ai_pro", price: 11900 },
    { key: "setup_full", price: 69000, billing: "once" as const },
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

test("one-time services are priced apart from the monthly total", () => {
  const priced = priceLines(catalog, { clients: 100, modules: { client_app: 1, setup_full: 1 } });
  assert.equal(priced.total, 9900 + 4900);
  assert.deepEqual(priced.once, [{ key: "setup_full", quantity: 1, amount: 69000 }]);
  assert.equal(priced.onceTotal, 69000);
});

test("tiers: choosing one replaces the others and brings what it needs", () => {
  const pro = chooseTier("client_app", "pro", {}, catalog);
  assert.deepEqual(pro, { client_app: 1, client_app_branded: 1 });
  assert.equal(tierOf("client_app", pro), "pro");
  assert.deepEqual(chooseTier("client_app", "basic", pro, catalog), { client_app: 1 });
  assert.deepEqual(chooseTier("client_app", null, pro, catalog), {});
  // AI replies on WhatsApp need an AI tier: AI Basic comes along, an existing tier stays.
  assert.deepEqual(chooseTier("whatsapp", "pro", {}, catalog), { whatsapp: 1, whatsapp_ai: 1, ai_basic: 1 });
  assert.deepEqual(chooseTier("whatsapp", "pro", { ai_pro: 1 }, catalog), { ai_pro: 1, whatsapp: 1, whatsapp_ai: 1 });
  assert.equal(tierOf("support", {}), null);
});

test("removing a module removes what depends on it", () => {
  assert.deepEqual(withoutOrphans({ client_app_branded: 1, whatsapp: 1, whatsapp_ai: 1 }, catalog), { whatsapp: 1 });
});
