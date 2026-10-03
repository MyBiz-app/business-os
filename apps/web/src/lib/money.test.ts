import assert from "node:assert/strict";
import { test } from "node:test";

import { formatMoney, toMajorUnits, toMinorUnits } from "./money.ts";

test("parses major units into minor units", () => {
  assert.equal(toMinorUnits("60"), 6000);
  assert.equal(toMinorUnits("59.9"), 5990);
  assert.equal(toMinorUnits("59,90"), 5990);
  assert.equal(toMinorUnits("0.07"), 7);
  assert.equal(toMinorUnits(""), 0);
  assert.equal(toMinorUnits("-5"), null);
  assert.equal(toMinorUnits("1.234"), null);
  assert.equal(toMinorUnits("abc"), null);
});

test("formats minor units back for inputs and display", () => {
  assert.equal(toMajorUnits(6000), "60");
  assert.equal(toMajorUnits(5990), "59.90");
  assert.match(formatMoney(5990, "ILS", "he"), /59\.90/);
  assert.match(formatMoney(5990, "USD", "en"), /\$59\.90/);
  assert.match(formatMoney(12000, "ILS", "he"), /120(?!\.)/);
});
