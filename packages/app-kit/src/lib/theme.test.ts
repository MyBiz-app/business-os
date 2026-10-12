import assert from "node:assert/strict";
import { test } from "node:test";

import { colors, paletteFor } from "./theme.ts";

test("paletteFor keeps the palette as is without high contrast", () => {
  assert.deepEqual(paletteFor("light", false), colors.light);
});

test("paletteFor darkens muted text and borders in high contrast", () => {
  const high = paletteFor("light", true);
  assert.notEqual(high.muted, colors.light.muted);
  assert.notEqual(high.border, colors.light.border);
  assert.equal(high.primary, colors.light.primary);
});
