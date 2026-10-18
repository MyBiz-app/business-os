import assert from "node:assert/strict";
import { test } from "node:test";

import { businessNumberOk, businessSize, calcPlanQuery, normalizeWebsiteUrl, clientsTier, companyPrefixWarning, modulesFromParam, wholeParam, chooseTier, decodePlan, encodePlan, priceLines, type SignupPlan, tierOf, withLocations, withoutOrphans } from "./signup-plan.ts";

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
  assert.equal(decodePlan(encodePlan({ ...plan, vertical: "no_such_industry" as "beauty" })), null);
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

test("an Israeli business number needs a valid check digit; abroad it is optional", () => {
  assert.equal(businessNumberOk("ILS", "000000018"), true);
  assert.equal(businessNumberOk("ILS", "000-000-018"), true);
  assert.equal(businessNumberOk("ILS", "123456789"), false);
  assert.equal(businessNumberOk("ILS", ""), false);
  assert.equal(businessNumberOk("USD", ""), true);
  assert.equal(decodePlan(encodePlan({ ...plan, businessNumber: "000 000 018" }))?.businessNumber, "000000018");
});

test("the company prefix warning is soft and only for Israeli companies", () => {
  assert.equal(companyPrefixWarning("ILS", "company", "000000018"), true);
  assert.equal(companyPrefixWarning("ILS", "company", "515555555"), false);
  assert.equal(companyPrefixWarning("ILS", "licensed_dealer", "000000018"), false);
  assert.equal(companyPrefixWarning("USD", "company", "000000018"), false);
  assert.equal(companyPrefixWarning("ILS", "company", "123456789"), false); // invalid digit: the other error shows
  assert.equal(decodePlan(encodePlan({ ...plan, entityType: "exempt_dealer" }))?.entityType, "exempt_dealer");
  assert.equal(decodePlan(encodePlan({ ...plan, entityType: "bogus" as never }))?.entityType, undefined);
});

test("a client count lands in the right core tier", () => {
  assert.equal(clientsTier(0), 100);
  assert.equal(clientsTier(100), 100);
  assert.equal(clientsTier(101), 300);
  assert.equal(clientsTier(240), 300);
  assert.equal(clientsTier(1000), 1000);
  assert.equal(clientsTier(1001), 1500);
});

test("the calculator plan round-trips through the /start link", () => {
  const query = new URLSearchParams(calcPlanQuery({ vertical: "beauty", clients: 240, locations: 2, currency: "ILS", modules: { client_app: 1, ai_basic: 1, extra_location: 1 } }));
  assert.equal(query.get("from"), "calc");
  assert.equal(query.get("vertical"), "beauty");
  assert.equal(query.get("modules"), "client_app,ai_basic");
  assert.deepEqual(modulesFromParam(query.get("modules")), { client_app: 1, ai_basic: 1 });
  assert.equal(wholeParam(query.get("clients"), 0, 100000, 100), 240);
  assert.equal(wholeParam("abc", 0, 10, 7), 7);
  assert.deepEqual(modulesFromParam("client_app,evil"), { client_app: 1 });
});

test("the price at 240 clients, 2 locations and the app", () => {
  const { total } = priceLines(catalog, { clients: 240, modules: withLocations({ client_app: 1 }, 2) });
  assert.equal(total, 14900 + 4900 + 2900);
});

test("business size: alone, 2-5, 6-20, or a network of branches", () => {
  assert.equal(businessSize(1, 1), "solo");
  assert.equal(businessSize(2, 1), "small");
  assert.equal(businessSize(5, 1), "small");
  assert.equal(businessSize(6, 1), "medium");
  assert.equal(businessSize(20, 1), "medium");
  assert.equal(businessSize(21, 1), "network");
  assert.equal(businessSize(1, 2), "network");
});

test("a website address is accepted with or without the scheme, anything else is not", () => {
  assert.equal(normalizeWebsiteUrl("www.example.co.il"), "https://www.example.co.il/");
  assert.equal(normalizeWebsiteUrl(" https://example.com/page "), "https://example.com/page");
  assert.equal(normalizeWebsiteUrl("http://example.com"), "http://example.com/");
  assert.equal(normalizeWebsiteUrl(""), null);
  assert.equal(normalizeWebsiteUrl("not a site"), null);
  assert.equal(normalizeWebsiteUrl("localhost"), null);
  assert.equal(normalizeWebsiteUrl("javascript://example.com/%0Aalert(1)"), null);
});

test("the website step survives the URL: kept for 'have', ignored otherwise", () => {
  const have = decodePlan(encodePlan({ ...plan, site: "have", websiteUrl: "www.shira.co.il" }));
  assert.equal(have?.site, "have");
  assert.equal(have?.websiteUrl, "https://www.shira.co.il/");
  const build = decodePlan(encodePlan({ ...plan, site: "build", websiteUrl: "www.shira.co.il" }));
  assert.equal(build?.site, "build");
  assert.equal(build?.websiteUrl, undefined);
  assert.equal(decodePlan(encodePlan({ ...plan, site: "huh" as never }))?.site, undefined);
});

test("a website built for a business with the system is a monthly line and a setup line", () => {
  const withSite = { ...catalog, currency: "ILS" };
  const { lines, total, once, onceTotal } = priceLines(withSite, { ...plan, site: "build" });
  assert.deepEqual(lines.at(-1), { key: "website", quantity: 1, amount: 2900 });
  assert.equal(total, 25600 + 2900);
  assert.deepEqual(once, [{ key: "website", quantity: 1, amount: 49000 }]);
  assert.equal(onceTotal, 49000);
  assert.equal(priceLines(withSite, { ...plan, site: "have" }).total, 25600);
});

test("a website-only plan pays the stand-alone price and has no core plan or modules", () => {
  const { lines, once } = priceLines({ ...catalog, currency: "ILS" }, { clients: 0, modules: { client_app: 1 }, track: "website_only" });
  assert.deepEqual(lines, [{ key: "website", quantity: 1, amount: 4900 }]);
  assert.deepEqual(once, [{ key: "website", quantity: 1, amount: 79000 }]);
  const decoded = decodePlan(encodePlan({ ...plan, modules: {}, track: "website_only" }));
  assert.equal(decoded?.track, "website_only");
  assert.equal(decodePlan(encodePlan(plan))?.track, undefined);
});
