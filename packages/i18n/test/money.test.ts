import assert from "node:assert/strict";
import { test } from "node:test";

import { formatMoney, minorDigits, toMajor, toMajorUnits, toMinorUnits } from "../src/money.ts";

test("parses major units into minor units", () => {
  assert.equal(toMinorUnits("60", "ILS"), 6000);
  assert.equal(toMinorUnits("59.9", "ILS"), 5990);
  assert.equal(toMinorUnits("59,90", "ILS"), 5990);
  assert.equal(toMinorUnits("0.07", "ILS"), 7);
  assert.equal(toMinorUnits("", "ILS"), 0);
  assert.equal(toMinorUnits("-5", "ILS"), null);
  assert.equal(toMinorUnits("1.234", "ILS"), null);
  assert.equal(toMinorUnits("abc", "ILS"), null);
});

test("formats minor units back for inputs and display", () => {
  assert.equal(toMajorUnits(6000, "ILS"), "60");
  assert.equal(toMajorUnits(5990, "ILS"), "59.90");
  assert.match(formatMoney(5990, "ILS", "he"), /59\.90/);
  assert.match(formatMoney(5990, "USD", "en"), /\$59\.90/);
  assert.match(formatMoney(12000, "ILS", "he"), /120(?!\.)/);
});

test("knows how many decimals each currency has", () => {
  assert.equal(minorDigits("ILS"), 2);
  assert.equal(minorDigits("USD"), 2);
  assert.equal(minorDigits("JPY"), 0);
  assert.equal(toMajor(5990, "ILS"), 59.9);
  assert.equal(toMajor(500, "JPY"), 500); // a yen has no smaller unit
  assert.equal(toMinorUnits("500", "JPY"), 500);
  assert.equal(toMinorUnits("5.5", "JPY"), null);
  assert.equal(toMajorUnits(500, "JPY"), "500");
  assert.match(formatMoney(500, "JPY", "en"), /¥500/);
});
