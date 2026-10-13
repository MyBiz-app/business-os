import assert from "node:assert/strict";
import { test } from "node:test";

import { Linter } from "eslint";

import direction from "../../eslint-rules/no-physical-classes.mjs";
import { inputDir, isolate } from "./bidi.ts";

test("inputDir: addresses and secrets are left to right, free text follows its letters", () => {
  for (const type of ["email", "tel", "url", "password", "number"]) assert.equal(inputDir(type), "ltr");
  for (const type of ["text", "search", undefined]) assert.equal(inputDir(type), "auto");
});

test("isolate wraps text in Unicode isolates", () => {
  assert.equal(isolate("Dana"), "⁨Dana⁩");
  assert.equal(isolate(null), "⁨⁩");
});

const linter = new Linter();
const lint = (code: string) =>
  linter.verify(
    code,
    [
      {
        files: ["**/*.js"],
        languageOptions: { ecmaVersion: 2022, sourceType: "module" },
        plugins: { direction },
        rules: { "direction/no-physical-classes": "error" },
      },
    ],
    "t.js",
  );

test("lint rule flags physical-side classes", () => {
  for (const cls of ["ml-2", "flex pr-4", "sm:text-left", "left-0", "-mr-1", "rounded-l-lg", "border-r", "hover:right-1/2"]) {
    assert.equal(lint(`const a = "${cls}";`).length, 1, cls);
  }
  assert.equal(lint("const a = `flex ml-${n}`;").length, 1);
});

test("lint rule allows logical classes and ordinary words", () => {
  for (const cls of ["ms-2 pe-4", "text-start", "start-0", "rounded-s-lg", "border-e", "Scroll to the left", "left"]) {
    assert.equal(lint(`const a = "${cls}";`).length, 0, cls);
  }
});
