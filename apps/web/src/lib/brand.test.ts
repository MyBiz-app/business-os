import assert from "node:assert/strict";
import { test } from "node:test";

import { brandStyle, contrastRatio, mix, readableOn, textOn } from "./brand.ts";

const SAMPLES = ["#4f46e5", "#0f766e", "#fde047", "#e11d48", "#22d3ee", "#7c3aed", "#b45309", "#000000", "#ffffff"];

test("contrast ratio matches WCAG reference values", () => {
  assert.equal(Math.round(contrastRatio("#ffffff", "#000000")), 21);
  assert.equal(contrastRatio("#777777", "#777777"), 1);
});

test("picks readable text for brand colors", () => {
  assert.equal(textOn("#4f46e5"), "#ffffff");
  assert.equal(textOn("#fde047"), "#18181b");
  for (const color of SAMPLES) {
    assert.ok(contrastRatio(color, textOn(color)) >= 4.5, color);
  }
});

test("brand color is adjusted to be readable on light and dark surfaces", () => {
  assert.equal(readableOn("#4f46e5", "#f4f4f5"), "#4f46e5"); // already fine: unchanged
  for (const color of SAMPLES) {
    for (const surface of ["#f4f4f5", "#18181b", "#ffffff", "#15151c"]) {
      const readable = readableOn(color, surface);
      assert.ok(contrastRatio(readable, surface) >= 4.5, `${color} on ${surface}`);
      assert.ok(contrastRatio(readable, mix(surface, readable, 0.1)) >= 4.5, `${color} on tint`);
      // Text on the brand color (a button) reads too: mid-tones like purple used to fail here.
      assert.ok(contrastRatio(readable, textOn(readable)) >= 4.5, `text on ${color} (${surface})`);
    }
  }
});

test("no brand color means no overrides", () => {
  assert.equal(brandStyle(null), undefined);
  const style = brandStyle("#0f766e") as Record<string, string>;
  assert.ok(contrastRatio(style["--brand"], "#f4f4f5") >= 4.5);
  assert.notEqual(style["--brand-dark"], "#0f766e"); // lightened for dark mode
});
