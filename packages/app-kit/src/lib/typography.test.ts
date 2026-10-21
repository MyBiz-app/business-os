import assert from "node:assert/strict";
import { test } from "node:test";

import { familyFor, familyForLocale, scaleText } from "./typography.ts";

test("a font weight picks the matching Assistant file", () => {
  assert.equal(familyFor(undefined), "Assistant_400Regular");
  assert.equal(familyFor("400"), "Assistant_400Regular");
  assert.equal(familyFor(500), "Assistant_500Medium");
  assert.equal(familyFor("600"), "Assistant_600SemiBold");
  assert.equal(familyFor("bold"), "Assistant_600SemiBold");
  assert.equal(familyFor("800"), "Assistant_600SemiBold");
});

test("semibold English text uses the display face, Hebrew stays in Assistant", () => {
  assert.equal(familyForLocale("600", "en"), "PlusJakartaSans_600SemiBold");
  assert.equal(familyForLocale("600", "he"), "Assistant_600SemiBold");
  assert.equal(familyForLocale("400", "en"), "Assistant_400Regular");
});

test("text size scales font size and line height", () => {
  assert.deepEqual(scaleText({ fontSize: 16, lineHeight: 24 }, 1.25), { fontSize: 20, lineHeight: 30 });
  assert.deepEqual(scaleText({ fontSize: 16 }, 1), { fontSize: 16 });
  assert.deepEqual(scaleText({}, 1.125), { fontSize: 15.8 });
});
