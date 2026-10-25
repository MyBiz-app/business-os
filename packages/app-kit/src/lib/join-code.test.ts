import assert from "node:assert/strict";
import { test } from "node:test";

import { joinCodeFromScan } from "./join-code.ts";

test("a join code is found in a bare code, an app link and a web link", () => {
  assert.equal(joinCodeFromScan(" ab12cd34 "), "AB12CD34");
  assert.equal(joinCodeFromScan("mybiz://join?code=ab12cd34"), "AB12CD34");
  assert.equal(joinCodeFromScan("https://app.example.com/join/AB12CD34?utm=x"), "AB12CD34");
});

test("text that is not a code gives null", () => {
  assert.equal(joinCodeFromScan("https://example.com/menu"), null);
  assert.equal(joinCodeFromScan("hello world"), null);
  assert.equal(joinCodeFromScan(""), null);
});
