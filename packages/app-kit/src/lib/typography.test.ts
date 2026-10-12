import assert from "node:assert/strict";
import { test } from "node:test";

import { familyFor, familyForLocale, scaleText } from "./typography.ts";

test("a font weight picks the matching Heebo file", () => {
  assert.equal(familyFor(undefined), "Heebo_400Regular");
  assert.equal(familyFor("400"), "Heebo_400Regular");
  assert.equal(familyFor("600"), "Heebo_500Medium");
  assert.equal(familyFor(500), "Heebo_500Medium");
  assert.equal(familyFor("700"), "Heebo_700Bold");
  assert.equal(familyFor("bold"), "Heebo_700Bold");
  assert.equal(familyFor("800"), "Heebo_700Bold");
});

test("bold English text uses the display face, Hebrew stays in Heebo", () => {
  assert.equal(familyForLocale("700", "en"), "PlusJakartaSans_700Bold");
  assert.equal(familyForLocale("700", "he"), "Heebo_700Bold");
  assert.equal(familyForLocale("400", "en"), "Heebo_400Regular");
});

test("text size scales font size and line height", () => {
  assert.deepEqual(scaleText({ fontSize: 16, lineHeight: 24 }, 1.25), { fontSize: 20, lineHeight: 30 });
  assert.deepEqual(scaleText({ fontSize: 16 }, 1), { fontSize: 16 });
  assert.deepEqual(scaleText({}, 1.125), { fontSize: 15.8 });
});
