import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { TERM_KEYS, termOf } from "../src/index.ts";

const messages = (locale: string) =>
  JSON.parse(readFileSync(new URL(`../../i18n/messages/${locale}.json`, import.meta.url), "utf8")) as {
    terms: Record<string, Record<string, string>>;
  };

test("the renameable words are exactly the translated ones, in every set and language", () => {
  for (const locale of ["he", "en"]) {
    for (const [set, words] of Object.entries(messages(locale).terms)) {
      const names = Object.keys(words).filter((name) => name !== "sessionsToday").sort();
      assert.deepEqual(names, [...TERM_KEYS].sort(), `${locale}.${set}`);
    }
  }
});

test("the owner's word wins in its language; everything else keeps the industry's", () => {
  const lookup = (path: string) => `default:${path}`;
  const business = { vertical: "gym", terms_override: { he: { clients: "חברי המועדון" } } };
  assert.equal(termOf(business, "he", "clients", lookup), "חברי המועדון");
  assert.equal(termOf(business, "he", "client", lookup), "default:fitness.client");
  assert.equal(termOf(business, "en", "clients", lookup), "default:fitness.clients");
  assert.equal(termOf({ vertical: "gym", terms_override: { he: { clients: "  " } } }, "he", "clients", lookup), "default:fitness.clients");
  assert.equal(termOf(null, "he", "clients", lookup).endsWith(".clients"), true);
});
