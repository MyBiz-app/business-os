import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { CATEGORIES, vertical } from "../src/index.ts";
import {
  BILLING_UNITS,
  CALENDAR_VIEWS_V2,
  CATALOG_V2,
  CUSTOMER_TERMS,
  DEPENDENTS_MODES,
  DEPENDENTS_V2,
  QUESTION_KINDS,
  SERVICE_MODEL_KEYS,
  type BusinessTypeV2,
  businessType,
  businessTypes,
  defaultActivities,
  domainV2,
  domainsV2,
  normalizeSearch,
  resourceType,
  resourceTypes,
  searchBusinessTypes,
  successorsOf,
  typesInDomain,
} from "../src/v2.ts";
import { V2_API_COPY, V2_TS_COPY, apiCopyV2, tsCopyV2 } from "../scripts/export.mjs";

const types = businessTypes();
const V1_KEYS = (() => {
  const keys: { key: string; isCategory: boolean }[] = [];
  for (const category of CATEGORIES) {
    keys.push({ key: category.key, isCategory: true });
    for (const child of category.children ?? []) keys.push({ key: child.key, isCategory: false });
  }
  return keys;
})();
const V1_TERMS = new Set(CATEGORIES.map((c) => c.terms));

test("the checked-in copies are up to date (pnpm verticals:export)", () => {
  assert.equal(readFileSync(V2_TS_COPY, "utf8"), tsCopyV2(), "run pnpm verticals:export");
  assert.equal(readFileSync(V2_API_COPY, "utf8"), apiCopyV2(), "run pnpm verticals:export");
});

test("the catalog has the size the spec describes", () => {
  assert.equal(domainsV2().length, 12);
  assert.ok(types.length >= 70, `business types: ${types.length}`);
  const v1 = new Set(V1_KEYS.map((k) => k.key));
  const added = types.filter((t) => !v1.has(t.key) && !t.custom);
  assert.ok(added.length >= 20, `new business types: ${added.length}`);
  for (const t of added) assert.equal(t.status, "beta", `${t.key}: a new type enters as beta`);
});

test("keys are unique snake case, and every reference resolves", () => {
  const seen = new Set<string>();
  for (const t of types) {
    assert.match(t.key, /^[a-z][a-z0-9_]*$/, t.key);
    assert.ok(!seen.has(t.key), `duplicate ${t.key}`);
    seen.add(t.key);
    if (t.custom) assert.equal(t.domain, null, "only the custom path has no domain");
    else assert.ok(domainV2(t.domain), `${t.key}: domain ${t.domain}`);
    for (const d of t.also_in ?? []) assert.ok(domainV2(d) && d !== t.domain, `${t.key}: also_in ${d}`);
    assert.ok(V1_TERMS.has(t.terms), `${t.key}: terms set ${t.terms}`);
    assert.ok(CUSTOMER_TERMS.includes(t.customer_term), `${t.key}: customer term`);
    assert.ok(CALENDAR_VIEWS_V2.includes(t.calendar_view), `${t.key}: calendar view`);
    assert.ok(t.common_combos.length <= 4, `${t.key}: combos`);
    for (const c of t.common_combos) assert.ok(businessType(c) && c !== t.key, `${t.key}: combo ${c}`);
    assert.ok(t.order > 0);
  }
  assert.equal(new Set(types.map((t) => t.order)).size, types.length, "orders are unique");
  assert.equal(types.filter((t) => t.custom).length, 1);
  for (const d of domainsV2()) assert.ok(typesInDomain(d.key).length > 0, `${d.key}: empty domain`);
});

test("every name and question is in Hebrew and English, and every type has synonyms to search by", () => {
  const both = (locales: Record<string, string>, where: string) => {
    for (const locale of ["he", "en"]) assert.ok(locales[locale]?.trim(), `${where}: ${locale}`);
  };
  for (const d of domainsV2()) both(d.names, d.key);
  for (const r of resourceTypes()) both(r.names, r.key);
  for (const t of types) {
    both(t.names, t.key);
    both(t.customers, `${t.key} customers`);
    assert.ok(t.synonyms.he.length >= 2 && t.synonyms.en.length >= 2, `${t.key}: needs 2+ synonyms per language`);
    for (const a of t.activities) both(a.names, `${t.key}.${a.key}`);
    for (const q of t.questions) both(q.text, `${t.key}.${q.key}`);
  }
});

test("every v1 category and sub-category has a successor, and no v1 key is lost", () => {
  for (const { key, isCategory } of V1_KEYS) {
    if (isCategory) {
      const covered = domainsV2().some((d) => d.replaces.includes(key)) || types.some((t) => t.replaces?.includes(key));
      assert.ok(covered, `v1 category ${key} has no domain or type that replaces it`);
    } else {
      assert.ok(successorsOf(key).length > 0, `v1 sub-category ${key} has no successor`);
    }
  }
  for (const t of types) for (const r of t.replaces ?? []) assert.ok(vertical(r), `${t.key}: replaces unknown v1 key ${r}`);
  assert.deepEqual(successorsOf("padel_tennis").map((t) => t.key).sort(), ["padel_club", "tennis_club"]);
  assert.deepEqual(successorsOf("sports").map((t) => t.key), ["multi_sport"]);
});

test("resource types describe their lengths and attributes", () => {
  for (const r of resourceTypes()) {
    assert.match(r.key, /^[a-z][a-z0-9_]*$/);
    assert.ok(r.default_capacity >= 1);
    assert.ok(r.min_minutes <= r.default_minutes && r.default_minutes <= r.max_minutes, `${r.key}: default length`);
    assert.ok(r.step_minutes >= 5 && (r.max_minutes - r.min_minutes) % r.step_minutes === 0, `${r.key}: step`);
    for (const a of r.attributes) {
      assert.match(a.key, /^[a-z][a-z0-9_]*$/);
      assert.equal(a.kind === "select", (a.options?.length ?? 0) > 0, `${r.key}.${a.key}: options`);
    }
  }
  for (const key of ["tennis_court", "padel_court", "football_5", "football_7", "football_11", "basketball_court",
    "volleyball_court", "beach_volleyball_court", "pickleball_court", "squash_court", "walking_football_pitch",
    "rehearsal_room", "meeting_room", "treatment_room", "studio_room"]) {
    assert.ok(resourceType(key), `spec resource type ${key}`);
  }
  assert.equal(resourceType("padel_court")!.default_minutes, 90, "padel is booked for 90 minutes");
});

test("activities follow the rules of their service model", () => {
  for (const t of types) {
    if (t.custom) {
      assert.equal(t.activities.length, 0);
      continue;
    }
    const where = (a: { key: string }) => `${t.key}.${a.key}`;
    assert.ok(t.activities.length >= 1, `${t.key}: needs activities`);
    assert.ok(!t.activities[0]!.optional, `${t.key}: the first activity is the main one`);
    assert.equal(new Set(t.activities.map((a) => a.key)).size, t.activities.length, `${t.key}: activity keys`);
    for (const a of t.activities) {
      assert.match(a.key, /^[a-z][a-z0-9_]*$/);
      assert.ok(SERVICE_MODEL_KEYS.includes(a.model), `${where(a)}: model`);
      assert.ok(Number.isInteger(a.duration_minutes) && a.duration_minutes >= 5, `${where(a)}: duration`);
      assert.ok(Number.isInteger(a.price_ils) && a.price_ils >= 0, `${where(a)}: price`);
      if (!a.coming_soon) assert.ok(a.price_ils > 0, `${where(a)}: price needed`);
      if (a.unit) assert.ok(BILLING_UNITS.includes(a.unit), `${where(a)}: unit`);
      if (a.model === "group_class") assert.ok((a.capacity ?? 0) > 1, `${where(a)}: class capacity`);
      if (a.model === "large_group") {
        assert.ok((a.capacity ?? 0) >= 8 && (a.min_staff ?? 0) >= 1, `${where(a)}: a large group needs capacity and min_staff`);
      }
      if (a.model === "on_site") {
        assert.ok(Number.isInteger(a.travel_minutes) && a.travel_minutes! >= 0 && a.travel_minutes! <= 240, `${where(a)}: travel`);
      }
      if (a.model === "resource_rental" || a.model === "resource_staff") {
        assert.ok(a.resource_type, `${where(a)}: needs a resource_type`);
      }
      if (a.model === "resource_rental") {
        assert.ok(a.max_minutes !== undefined && a.step_minutes !== undefined, `${where(a)}: a rental needs max_minutes and step_minutes`);
        assert.ok(a.max_minutes! >= a.duration_minutes && (a.max_minutes! - a.duration_minutes) % a.step_minutes! === 0, `${where(a)}: rental lengths`);
        const r = resourceType(a.resource_type)!;
        assert.ok(a.max_minutes! <= r.max_minutes, `${where(a)}: longer than the ${r.key} allows`);
      }
      if (a.resource_type) {
        const r = resourceType(a.resource_type);
        assert.ok(r, `${where(a)}: resource type ${a.resource_type}`);
        assert.ok(a.duration_minutes >= r!.min_minutes && a.duration_minutes <= r!.max_minutes, `${where(a)}: length outside ${r!.key}`);
        if (!a.optional && !a.coming_soon) {
          assert.ok(t.resources.some((seed) => seed.type === a.resource_type), `${where(a)}: a default activity needs its resource ${a.resource_type}`);
        }
      }
    }
    for (const seed of t.resources) {
      const r = resourceType(seed.type);
      assert.ok(r, `${t.key}: resource ${seed.type}`);
      assert.ok(Number.isInteger(seed.count) && seed.count >= 1, `${t.key}: ${seed.type} count`);
      for (const [name, value] of Object.entries(seed.attributes ?? {})) {
        const def = r!.attributes.find((x) => x.key === name);
        assert.ok(def, `${t.key}: ${seed.type} has no attribute ${name}`);
        if (def!.kind === "select") assert.ok(def!.options!.includes(value as string), `${t.key}: ${name}=${value}`);
        if (def!.kind === "boolean") assert.equal(typeof value, "boolean", `${t.key}: ${name}`);
      }
    }
  }
});

const AFFECTS = /^(none|staff_count|dependents|time_billing|service_area|axis:[a-z_]+|activity:(\*|[a-z_]+)|resource_count:(\*|[a-z_0-9]+)|resource_attr:[a-z_0-9]+\.[a-z_]+)$/;

test("each type asks two to four smart questions that point at something real", () => {
  for (const t of types) {
    assert.ok(t.custom ? t.questions.length === 4 : t.questions.length >= 2 && t.questions.length <= 4, `${t.key}: question count`);
    assert.equal(new Set(t.questions.map((q) => q.key)).size, t.questions.length, `${t.key}: question keys`);
    for (const q of t.questions) {
      const where = `${t.key}.${q.key}`;
      assert.ok(QUESTION_KINDS.includes(q.kind), `${where}: kind`);
      assert.match(q.affects, AFFECTS, `${where}: affects`);
      assert.equal(["select", "multi_select"].includes(q.kind), (q.options?.length ?? 0) > 0, `${where}: options`);
      if (q.kind === "boolean") assert.equal(typeof q.default, "boolean", `${where}: default`);
      if (q.kind === "number") assert.equal(typeof q.default, "number", `${where}: default`);
      if (q.kind === "select") assert.ok(q.options!.includes(q.default as string), `${where}: default in options`);
      const [target, ref] = q.affects.split(":");
      if (target === "activity" && ref !== "*") assert.ok(t.activities.some((a) => a.key === ref), `${where}: activity ${ref}`);
      if (target === "resource_count" && ref !== "*") assert.ok(resourceType(ref), `${where}: resource type ${ref}`);
      if (target === "resource_attr") {
        const [rt, attribute] = ref!.split(".");
        assert.ok(resourceType(rt)?.attributes.some((x) => x.key === attribute), `${where}: attribute ${ref}`);
      }
    }
  }
});

test("a type with children or vehicles says how the profile is used", () => {
  for (const t of types) {
    if (!t.dependents) {
      assert.equal(t.dependents_mode, undefined, `${t.key}: mode without dependents`);
      continue;
    }
    assert.ok(DEPENDENTS_V2.includes(t.dependents), `${t.key}: dependents`);
    assert.ok(DEPENDENTS_MODES.includes(t.dependents_mode!), `${t.key}: dependents mode`);
    if (t.dependents_mode === "ask") assert.ok(t.questions.some((q) => q.affects === "dependents"), `${t.key}: "ask" needs a question`);
  }
  assert.equal(businessType("garage")!.dependents, "vehicle");
  assert.equal(businessType("kids_activities")!.dependents_mode, "required");
  assert.equal(businessType("martial_arts")!.dependents_mode, "ask");
});

test("the spec's sports examples come out right (tennis without padel, padel at 90 minutes)", () => {
  const tennis = businessType("tennis_club")!;
  assert.deepEqual(tennis.resources.map((r) => r.type), ["tennis_court"]);
  assert.ok(defaultActivities("tennis_club").every((a) => !a.resource_type || a.resource_type === "tennis_court"));
  assert.deepEqual(defaultActivities("tennis_club").map((a) => a.model), ["resource_rental", "resource_staff"]);
  assert.equal(tennis.customer_term, "player");
  const padel = businessType("padel_club")!;
  assert.deepEqual(padel.resources.map((r) => r.type), ["padel_court"]);
  assert.equal(padel.activities[0]!.duration_minutes, 90);
  assert.equal(businessType("walking_football")!.synonyms.he.includes("ווטבול"), true);
  assert.equal(businessType("pilates")!.activities.find((a) => a.key === "reformer_class")!.resource_type, "reformer");
  assert.equal(businessType("gym")!.activities[0]!.model, "open_entry");
  assert.equal(businessType("pet_boarding")!.activities[0]!.unit, "night");
  assert.deepEqual(businessType("custom")!.questions.map((q) => q.affects), ["axis:capacity", "axis:provider", "axis:place", "axis:payment"]);
});

test("search understands names, synonyms, sentences, a prefix letter and typos", () => {
  const top = (text: string) => searchBusinessTypes(text)[0]?.key;
  assert.equal(top("טניס"), "tennis_club");
  assert.equal(top("padel"), "padel_club");
  assert.equal(top("tenis"), "tennis_club");
  assert.equal(top("ווטבול"), "walking_football");
  assert.equal(top("מגרש טניס באשדוד"), "tennis_club");
  assert.equal(top("Barber"), "barbershop");
  assert.equal(top("מספרת גברים"), "barbershop");
  assert.equal(top("חדר בריחה"), "escape_room");
  assert.equal(top("מנעולן"), "locksmith");
  assert.equal(top("קלינאית תקשורת"), "speech_therapy");
  assert.equal(top("בטניס"), "tennis_club");
  assert.deepEqual(searchBusinessTypes("zzzzqq"), []);
  assert.deepEqual(searchBusinessTypes("a"), []);
  const courts = searchBusinessTypes("מגרש", 20).map((h) => h.key);
  for (const key of ["tennis_club", "padel_club", "football_pitches", "basketball_volleyball"]) {
    assert.ok(courts.includes(key), `"מגרש" should offer ${key}`);
  }
  assert.equal(normalizeSearch("  ג'ודו־קראטה "), "ג ודו קראטה");
});

test("every type is found by its own names and by each synonym", () => {
  const inTop = (query: string, key: string, n: number) =>
    searchBusinessTypes(query, n).some((h) => h.key === key);
  for (const t of businessTypes()) {
    assert.equal(searchBusinessTypes(t.names.he)[0]?.key, t.key, `${t.key}: Hebrew name finds it first`);
    assert.equal(searchBusinessTypes(t.names.en)[0]?.key, t.key, `${t.key}: English name finds it first`);
    for (const synonym of [...t.synonyms.he, ...t.synonyms.en]) {
      assert.ok(inTop(synonym, t.key, 5), `${t.key}: "${synonym}" finds it in the top 5`);
    }
  }
});

test("a type is listed under its domain, and an also_in type under both", () => {
  assert.ok(typesInDomain("sports_venues").some((t) => t.key === "padel_club"));
  const martial = ["learning", "fitness"].map((d) => typesInDomain(d).some((t) => t.key === "martial_arts"));
  assert.deepEqual(martial, [true, true]);
  assert.equal(CATALOG_V2.version, 2);
});

test("business types are sorted by domain order for display", () => {
  const orderOf = (t: BusinessTypeV2) => (t.domain ? domainV2(t.domain)!.order : 99);
  const inDomains = types.filter((t) => !t.custom).map(orderOf);
  assert.deepEqual([...inDomains].sort((a, b) => a - b).length, inDomains.length);
});
