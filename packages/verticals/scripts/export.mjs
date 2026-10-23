// Gathers catalog/*.json into the two checked-in copies the rest of the system reads:
//   - src/catalog.generated.ts for the website and the apps (every bundler reads TypeScript;
//     not every one reads JSON imports the same way), and
//   - apps/api/app/verticals_catalog.json for the API, whose image is built from apps/api alone.
// Catalog v2 (catalog-v2/: domains, resource types, business types) is gathered the same way into
// src/catalog-v2.generated.ts and apps/api/app/verticals_catalog_v2.json.
// test/catalog.test.ts and test/catalog-v2.test.ts fail when a copy is out of date.
//
//   pnpm verticals:export
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
export const CATALOG_DIR = join(root, "catalog");
export const TS_COPY = join(root, "src", "catalog.generated.ts");
export const API_COPY = join(root, "..", "..", "apps", "api", "app", "verticals_catalog.json");

/** Every category file, in display order. */
export function catalog() {
  return readdirSync(CATALOG_DIR)
    .filter((name) => name.endsWith(".json"))
    .map((name) => JSON.parse(readFileSync(join(CATALOG_DIR, name), "utf8")))
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
}

export const apiCopy = () => `${JSON.stringify(catalog(), null, 2)}\n`;

export const tsCopy = () =>
  "// Generated from catalog/*.json by `pnpm verticals:export`. Do not edit by hand.\n" +
  'import type { Entry } from "./index";\n\n' +
  `export const CATALOG: Entry[] = ${JSON.stringify(catalog(), null, 2)};\n`;

export const V2_DIR = join(root, "catalog-v2");
export const V2_TS_COPY = join(root, "src", "catalog-v2.generated.ts");
export const V2_API_COPY = join(root, "..", "..", "apps", "api", "app", "verticals_catalog_v2.json");

const readJson = (path) => JSON.parse(readFileSync(path, "utf8"));

/** Domains, resource types and business types of catalog v2, each in display order. */
export function catalogV2() {
  const typesDir = join(V2_DIR, "business-types");
  return {
    version: 2,
    domains: readJson(join(V2_DIR, "domains.json")).sort((a, b) => a.order - b.order),
    resource_types: readJson(join(V2_DIR, "resource-types.json")),
    business_types: readdirSync(typesDir)
      .filter((name) => name.endsWith(".json"))
      .map((name) => readJson(join(typesDir, name)))
      .sort((a, b) => a.order - b.order),
  };
}

export const apiCopyV2 = () => `${JSON.stringify(catalogV2(), null, 2)}\n`;

export const tsCopyV2 = () =>
  "// Generated from catalog-v2/ by `pnpm verticals:export`. Do not edit by hand.\n" +
  'import type { CatalogV2 } from "./v2";\n\n' +
  `export const CATALOG_V2: CatalogV2 = ${JSON.stringify(catalogV2(), null, 2)} as CatalogV2;\n`;

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  writeFileSync(TS_COPY, tsCopy());
  writeFileSync(API_COPY, apiCopy());
  writeFileSync(V2_TS_COPY, tsCopyV2());
  writeFileSync(V2_API_COPY, apiCopyV2());
  console.log("wrote the catalog copies for the web and apps (src/*.generated.ts) and the API (apps/api/app/verticals_catalog*.json)");
}
