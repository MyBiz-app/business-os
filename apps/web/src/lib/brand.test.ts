import assert from "node:assert/strict";
import { test } from "node:test";

import { brandStyle, contrastRatio, textOn } from "./brand.ts";

test("contrast ratio matches WCAG reference values", () => {
  assert.equal(Math.round(contrastRatio("#ffffff", "#000000")), 21);
  assert.equal(contrastRatio("#777777", "#777777"), 1);
});

test("picks readable text for brand colors", () => {
  assert.equal(textOn("#4f46e5"), "#ffffff");
  assert.equal(textOn("#0f766e"), "#ffffff");
  assert.equal(textOn("#fde047"), "#18181b");
  assert.equal(textOn("#ffffff"), "#18181b");
  for (const color of ["#4f46e5", "#0f766e", "#fde047", "#e11d48", "#22d3ee"]) {
    assert.ok(contrastRatio(color, textOn(color)) >= 4.5, color);
  }
});

test("no brand color means no overrides", () => {
  assert.equal(brandStyle(null), undefined);
});

