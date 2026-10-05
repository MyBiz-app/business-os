// Scaffolds a new industry: a category (its own catalog file) or a sub-category (an entry under
// its parent), plus placeholder texts in every language. The catalog tests then point at
// everything still to fill in; the entry starts as "planned" so nothing is open by accident.
//
//   pnpm vertical:new <key> [--parent <category-or-sub-category>]
//   pnpm vertical:new bakery
//   pnpm vertical:new kickboxing --parent classes
//
// Then: fill in the entry and the texts marked TODO, set its status to "live" (or "beta"),
// run `pnpm verticals:export` and `pnpm --filter @business-os/verticals test`.
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { CATALOG_DIR, catalog } from "./export.mjs";

const MESSAGES_DIR = join(CATALOG_DIR, "..", "..", "i18n", "messages");
const LOCALES = ["he", "en"];

const args = process.argv.slice(2);
const key = args.find((arg) => !arg.startsWith("--"));
const parentAt = args.indexOf("--parent");
const parent = parentAt >= 0 ? args[parentAt + 1] : null;

function fail(message) {
  console.error(message);
  process.exit(1);
}

if (!key || !/^[a-z][a-z0-9_]*$/.test(key)) fail("Usage: pnpm vertical:new <key> [--parent <key>] (key: lower_snake_case)");

/** Finds an entry by key in the catalog tree, with the category file it lives in. */
function find(target) {
  for (const category of catalog()) {
    const stack = [category];
    while (stack.length) {
      const entry = stack.pop();
      if (entry.key === target) return { category, entry };
      stack.push(...(entry.children ?? []));
    }
  }
  return null;
}

if (find(key)) fail(`"${key}" is already in the catalog.`);

const TODO = (what) => `TODO: ${what}`;
let texts;
if (parent) {
  const found = find(parent);
  if (!found) fail(`No catalog entry "${parent}".`);
  // A sub-category inherits everything; add only what differs (see docs/verticals.md).
  found.entry.children = [...(found.entry.children ?? []), { key, status: "planned" }];
  writeFileSync(join(CATALOG_DIR, `${found.category.key}.json`), `${JSON.stringify(found.category, null, 2)}\n`);
  texts = { name: TODO("name"), tagline: TODO("one-line tagline") };
  console.log(`added "${key}" under "${parent}" in catalog/${found.category.key}.json`);
} else {
  const order = Math.max(0, ...catalog().map((c) => c.order ?? 0)) + 1;
  const entry = {
    key,
    order,
    status: "planned",
    icon: "briefcase",
    color: "from-slate-500 to-slate-700",
    terms: key,
    client_term: "client",
    booking_modes: ["appointment"],
    cancellation_window_minutes: 1440,
    booking_requires_plan: false,
    default_preset: "growing",
    recommended_modules: [],
    client_fields: [],
    default_services: [],
    children: [],
  };
  writeFileSync(join(CATALOG_DIR, `${key}.json`), `${JSON.stringify(entry, null, 2)}\n`);
  texts = {
    name: TODO("name"),
    tagline: TODO("one-line tagline"),
    points: [TODO("benefit 1"), TODO("benefit 2"), TODO("benefit 3")],
    heroTitle: TODO("industry page title"),
    heroText: TODO("industry page text"),
    yours: TODO('"your studio"-style phrase'),
    example: TODO("example business name"),
  };
  console.log(`created catalog/${key}.json (copy "terms.fitness" to "terms.${key}" and adapt the words)`);
}

for (const locale of LOCALES) {
  const file = join(MESSAGES_DIR, `${locale}.json`);
  const messages = JSON.parse(readFileSync(file, "utf8"));
  messages.verticals = { ...messages.verticals, [key]: texts };
  writeFileSync(file, `${JSON.stringify(messages, null, 2)}\n`);
}
console.log(`added verticals.${key} to the translations (${LOCALES.join(", ")}) — fill in the TODOs`);
