import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const load = (locale) =>
  JSON.parse(readFileSync(new URL(`../messages/${locale}.json`, import.meta.url), "utf8"));

function keys(messages, prefix = "") {
  return Object.entries(messages).flatMap(([key, value]) =>
    typeof value === "object" ? keys(value, `${prefix}${key}.`) : [`${prefix}${key}`],
  );
}

test("every locale has exactly the same message keys", () => {
  const en = keys(load("en")).sort();
  const he = keys(load("he")).sort();
  assert.deepEqual(he, en);
});

test("no message is empty", () => {
  for (const locale of ["en", "he"]) {
    const messages = load(locale);
    for (const key of keys(messages)) {
      const value = key.split(".").reduce((node, part) => node[part], messages);
      assert.ok(String(value).trim().length > 0, `${locale}: ${key} is empty`);
    }
  }
});
