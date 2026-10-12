import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { ERROR_MESSAGES } from "./error-messages.ts";
import { render, scanClientNamespaces } from "../../scripts/client-namespaces.mjs";

const messages = (locale: string) =>
  JSON.parse(readFileSync(new URL(`../../../../packages/i18n/messages/${locale}.json`, import.meta.url), "utf8"));

test("the committed client namespace list is up to date (run `pnpm --filter web i18n:client`)", () => {
  const committed = readFileSync(new URL("../i18n/client-namespaces.ts", import.meta.url), "utf8");
  assert.equal(committed, render(scanClientNamespaces()));
});

test("every listed namespace exists in both languages", () => {
  const lists: Record<string, string[]> = scanClientNamespaces();
  for (const locale of ["he", "en"]) {
    const m = messages(locale);
    for (const [scope, list] of Object.entries(lists)) {
      for (const ns of list) assert.ok(ns in m, `${locale}: ${scope} lists unknown namespace ${ns}`);
    }
  }
});

test("the last-resort error page strings match the message files", () => {
  for (const locale of ["he", "en"] as const) {
    const m = messages(locale);
    assert.deepEqual(ERROR_MESSAGES[locale], {
      title: m.errorPages.title,
      text: m.errorPages.text,
      reference: m.errorPages.reference,
      retry: m.common.retry,
    });
  }
});
