// Gathers catalog/*.json into the two checked-in copies the rest of the system reads:
//   - src/catalog.generated.ts for the website and the apps (every bundler reads TypeScript;
//     not every one reads JSON imports the same way), and
//   - apps/api/app/verticals_catalog.json for the API, whose image is built from apps/api alone.
// test/catalog.test.ts fails when either is out of date.
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

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  writeFileSync(TS_COPY, tsCopy());
  writeFileSync(API_COPY, apiCopy());
  console.log("wrote packages/verticals/src/catalog.generated.ts and apps/api/app/verticals_catalog.json");
}
