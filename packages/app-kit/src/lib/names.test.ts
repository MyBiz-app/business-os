import assert from "node:assert/strict";
import { test } from "node:test";

import { fullName, initials } from "./names.ts";

test("initials take the first letter of the first two words", () => {
  assert.equal(initials("נועה כהן"), "נכ");
  assert.equal(initials("  dana   levi cohen "), "DL");
  assert.equal(initials("Maya"), "M");
  assert.equal(initials(""), "");
});

test("a full name skips missing parts", () => {
  assert.equal(fullName("Dana", "Levi"), "Dana Levi");
  assert.equal(fullName("Dana", null), "Dana");
  assert.equal(fullName("Dana", " "), "Dana");
});
