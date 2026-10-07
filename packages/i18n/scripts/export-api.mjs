// Copies the translations the API itself renders (emails, module names, default branch names, sample businesses) into the API package,
// because the API's container image is built from apps/api alone. The copy is checked in;
// test/messages.test.mjs fails when it is out of date.
//
//   pnpm --filter @business-os/i18n export:api
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
export const API_MESSAGES = join(root, "..", "..", "apps", "api", "app", "messages");
export const LOCALES = ["he", "en"];

/** The part of a locale's messages the API needs. */
export function apiMessages(locale) {
  const all = JSON.parse(readFileSync(join(root, "messages", `${locale}.json`), "utf8"));
  return {
    email: all.email,
    modules: { names: all.modules.names },
    locations: { mainBranch: all.locations.mainBranch, branchNumber: all.locations.branchNumber },
    samples: all.samples,
    bills: all.bills,
    verticals: Object.fromEntries(Object.entries(all.verticals).map(([key, texts]) => [key, { name: texts.name }])),
  };
}

export const serialize = (value) => `${JSON.stringify(value, null, 2)}\n`;

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  for (const locale of LOCALES) {
    writeFileSync(join(API_MESSAGES, `${locale}.json`), serialize(apiMessages(locale)));
    console.log(`wrote apps/api/app/messages/${locale}.json`);
  }
}
