import assert from "node:assert/strict";
import { test } from "node:test";

import { israeliIdValid, maskedId } from "../src/israeli-id.ts";

test("accepts numbers with a correct check digit, padded or not", () => {
  assert.equal(israeliIdValid("123456782"), true);
  assert.equal(israeliIdValid("12-345 6782"), true);
  assert.equal(israeliIdValid("18"), true);
});

test("rejects wrong check digits, letters, empty and too long", () => {
  for (const bad of ["123456789", "12345678a", "", "0", "000000000", "1234567890"]) {
    assert.equal(israeliIdValid(bad), false, bad);
  }
});

test("masks to the last four", () => {
  assert.equal(maskedId("6782"), "•••••6782");
});
