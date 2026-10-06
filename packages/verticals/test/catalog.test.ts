import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  ALL_VERTICALS,
  BOOKING_MODES,
  CATEGORIES,
  CURRENCIES,
  type Entry,
  FIELD_KINDS,
  ICONS,
  LOCALES,
  PRESETS,
  RECOMMENDABLE,
  STATUSES,
  categories,
  childrenOf,
  isOpen,
  termsOf,
  textKey,
  vertical,
} from "../src/index.ts";
import { API_COPY, TS_COPY, apiCopy, tsCopy } from "../scripts/export.mjs";

type Messages = Record<string, unknown>;
const messages: Record<string, Messages> = Object.fromEntries(
  LOCALES.map((locale) => [
    locale,
    JSON.parse(readFileSync(new URL(`../../i18n/messages/${locale}.json`, import.meta.url), "utf8")),
  ]),
);
const lookup = (locale: string, path: string): unknown =>
  path.split(".").reduce<unknown>((node, part) => (node as Messages | undefined)?.[part], messages[locale]);
const has = (locale: string) => (path: string) => lookup(locale, path) !== undefined;

function* entries(list: Entry[], parent: Entry | null = null): Generator<[Entry, Entry | null]> {
  for (const entry of list) {
    yield [entry, parent];
    yield* entries(entry.children ?? [], entry);
  }
}
const all = [...entries(CATEGORIES)];

test("the checked-in copies are up to date (pnpm verticals:export)", () => {
  assert.equal(readFileSync(TS_COPY, "utf8"), tsCopy(), "run pnpm verticals:export");
  assert.equal(readFileSync(API_COPY, "utf8"), apiCopy(), "run pnpm verticals:export");
});

test("keys are unique, lower snake case, and statuses known", () => {
  const seen = new Set<string>();
  for (const [entry] of all) {
    assert.match(entry.key, /^[a-z][a-z0-9_]*$/, entry.key);
    assert.ok(!seen.has(entry.key), `duplicate key ${entry.key}`);
    seen.add(entry.key);
    assert.ok(STATUSES.includes(entry.status), `${entry.key}: status`);
  }
  assert.equal(ALL_VERTICALS.length, seen.size);
});

test("every open category sets everything its sub-categories inherit", () => {
  for (const category of CATEGORIES.filter((c) => c.status !== "planned")) {
    for (const name of ["terms", "client_term", "booking_modes", "cancellation_window_minutes",
      "booking_requires_plan", "default_preset", "recommended_modules", "client_fields"] as const) {
      assert.notEqual(category[name], undefined, `${category.key}: ${name}`);
    }
  }
  for (const category of CATEGORIES) {
    assert.equal(typeof category.order, "number", `${category.key}: order`);
    assert.ok(ICONS.includes(category.icon as (typeof ICONS)[number]), `${category.key}: icon`);
    assert.match(category.color ?? "", /^from-\S+ to-\S+$/, `${category.key}: color`);
  }
});

test("a planned category has no sub-categories open for sign-up", () => {
  for (const [entry, parent] of all) {
    if (parent?.status === "planned") assert.equal(entry.status, "planned", entry.key);
  }
});

test("settings, starter content and client fields are valid", () => {
  for (const [entry] of all) {
    const where = entry.key;
    if (entry.icon) assert.ok(ICONS.includes(entry.icon as (typeof ICONS)[number]), `${where}: icon`);
    if (entry.default_preset) assert.ok(PRESETS.includes(entry.default_preset as (typeof PRESETS)[number]), `${where}: preset`);
    for (const module of entry.recommended_modules ?? []) {
      assert.ok(RECOMMENDABLE.includes(module as (typeof RECOMMENDABLE)[number]), `${where}: module ${module}`);
    }
    for (const mode of entry.booking_modes ?? []) {
      assert.ok(BOOKING_MODES.includes(mode as (typeof BOOKING_MODES)[number]), `${where}: mode ${mode}`);
    }
    for (const service of entry.default_services ?? []) {
      for (const locale of LOCALES) assert.ok(service.names[locale]?.trim(), `${where}: service name ${locale}`);
      assert.ok(service.duration_minutes >= 5 && service.duration_minutes <= 720, `${where}: duration`);
      assert.ok(BOOKING_MODES.includes(service.booking_mode), `${where}: booking mode`);
      assert.ok(Number.isInteger(service.prices.ILS) && service.prices.ILS! > 0, `${where}: ILS price`);
      for (const [currency, amount] of Object.entries(service.prices)) {
        assert.ok(CURRENCIES.includes(currency as (typeof CURRENCIES)[number]) && Number.isInteger(amount) && amount > 0, `${where}: ${currency}`);
      }
      assert.match(service.color, /^#[0-9a-f]{6}$/, `${where}: color`);
      if (service.booking_mode === "class") assert.ok((service.capacity ?? 0) > 1, `${where}: class capacity`);
      if (service.booking_mode === "resource") {
        const { duration_minutes: min, max_minutes: max, step_minutes: step } = service;
        assert.ok(max !== undefined && step !== undefined, `${where}: a resource needs max_minutes and step_minutes`);
        assert.ok(max >= min && (max - min) % step === 0 && step >= 15, `${where}: resource lengths`);
      }
    }
    for (const room of entry.default_rooms ?? []) {
      for (const locale of LOCALES) assert.ok(room.names[locale]?.trim(), `${where}: room name ${locale}`);
      assert.match(room.opens, /^\d\d:\d\d$/, `${where}: room opens`);
      assert.match(room.closes, /^\d\d:\d\d$/, `${where}: room closes`);
      assert.ok(room.closes > room.opens, `${where}: room hours`);
    }
    for (const plan of entry.default_plans ?? []) {
      for (const locale of LOCALES) assert.ok(plan.names[locale]?.trim(), `${where}: plan name ${locale}`);
      assert.ok(Number.isInteger(plan.prices.ILS) && plan.prices.ILS! > 0, `${where}: plan ILS price`);
      assert.ok(plan.kind === "membership" || (plan.credits ?? 0) > 0, `${where}: punch card credits`);
    }
    for (const field of [...(entry.client_fields ?? []), ...(entry.extra_client_fields ?? [])]) {
      assert.match(field.key, /^[a-z][a-z0-9_]*$/, `${where}: field ${field.key}`);
      assert.ok(FIELD_KINDS.includes(field.kind), `${where}: ${field.key} kind`);
      assert.equal(field.kind === "select", (field.options?.length ?? 0) > 0, `${where}: ${field.key} options`);
    }
  }
});

test("a sub-category inherits from its parent and overrides only what it sets", () => {
  const pilates = vertical("pilates")!;
  assert.equal(pilates.category, "fitness");
  assert.deepEqual(pilates.lineage, ["fitness", "pilates"]);
  assert.equal(pilates.terms, "fitness");
  assert.deepEqual(pilates.clientFields.map((f) => f.key), ["goal", "injuries"]);
  assert.deepEqual(vertical("physiotherapy")!.clientFields.map((f) => f.key).at(-1), "injury");
  assert.deepEqual(vertical("nails")!.clientFields.map((f) => f.key), ["allergies", "preferences"]);
  assert.equal(termsOf("garage"), "automotive");
  assert.equal(termsOf("no-such-industry"), "fitness");
  assert.deepEqual(categories().map((c) => c.key).slice(0, 5), ["fitness", "beauty", "clinic", "classes", "automotive"]);
  assert.ok(childrenOf("beauty").some((c) => c.key === "barbershop"));
  assert.ok(isOpen("garage") && !isOpen("pets") && !isOpen("nope"));
});

test("every entry has its texts in every language, with categories complete", () => {
  for (const locale of LOCALES) {
    for (const v of ALL_VERTICALS) {
      const own = (name: string) => lookup(locale, `verticals.${v.key}.${name}`);
      assert.ok(own("name"), `${locale}: verticals.${v.key}.name`);
      assert.ok(own("tagline"), `${locale}: verticals.${v.key}.tagline`);
      const required = v.depth === 0 ? ["points", "heroTitle", "heroText"] : [];
      if (v.depth === 0 && v.status !== "planned") required.push("yours", "example");
      for (const name of required) assert.ok(own(name), `${locale}: verticals.${v.key}.${name}`);
      for (const name of ["points", "heroTitle", "heroText", "yours", "example"]) {
        if (v.status !== "planned") assert.ok(has(locale)(textKey(v.key, name, has(locale))), `${locale}: ${v.key} ${name}`);
      }
      if (v.status !== "planned") {
        assert.ok(lookup(locale, `terms.${v.terms}.clients`), `${locale}: terms.${v.terms}`);
        for (const field of v.clientFields) {
          assert.ok(lookup(locale, `clientFields.${field.key}`), `${locale}: clientFields.${field.key}`);
          for (const option of field.options ?? []) {
            assert.ok(lookup(locale, `clientFields.${field.key}_options.${option}`), `${locale}: ${field.key} option ${option}`);
          }
        }
      }
    }
    for (const key of Object.keys(lookup(locale, "verticals") as Messages)) {
      assert.ok(vertical(key), `${locale}: verticals.${key} has no catalog entry`);
    }
  }
});

test("no placeholder from the generator is left (pnpm vertical:new)", () => {
  for (const locale of LOCALES) {
    const texts = JSON.stringify(lookup(locale, "verticals"));
    assert.ok(!texts.includes("TODO"), `${locale}: fill in the TODO texts under verticals`);
  }
});

test("a sub-category's text falls back to its category", () => {
  const he = has("he");
  assert.equal(textKey("pilates", "heroTitle", he), "verticals.fitness.heroTitle");
  assert.equal(textKey("pilates", "name", he), "verticals.pilates.name");
});

test("an industry by the hour starts with courts its services are booked in", () => {
  for (const v of ALL_VERTICALS.filter((entry) => entry.status !== "planned")) {
    const resources = v.defaultServices.filter((service) => service.booking_mode === "resource");
    if (resources.length > 0) assert.ok(v.defaultRooms.length > 0, `${v.key}: resource services need default_rooms`);
    if (resources.length > 0) assert.ok(v.bookingModes.includes("resource"), `${v.key}: booking_modes`);
  }
});
