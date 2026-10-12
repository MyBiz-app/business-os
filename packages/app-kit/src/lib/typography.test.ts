import assert from "node:assert/strict";
import { test } from "node:test";

import { familyFor } from "./typography.ts";

test("a font weight picks the matching Heebo file", () => {
  assert.equal(familyFor(undefined), "Heebo_400Regular");
  assert.equal(familyFor("400"), "Heebo_400Regular");
  assert.equal(familyFor("600"), "Heebo_500Medium");
  assert.equal(familyFor(500), "Heebo_500Medium");
  assert.equal(familyFor("700"), "Heebo_700Bold");
  assert.equal(familyFor("bold"), "Heebo_700Bold");
  assert.equal(familyFor("800"), "Heebo_700Bold");
});
