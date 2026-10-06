import assert from "node:assert/strict";
import { test } from "node:test";

import { visualRtl } from "./visual-rtl.ts";

test("Hebrew is laid out right to left for a renderer that draws left to right", () => {
  // Read from the right, the visual string spells the logical one.
  assert.equal(visualRtl("העסק שלך, מסודר."), ".רדוסמ ,ךלש קסעה");
  assert.equal(visualRtl("סוף סוף."), ".ףוס ףוס");
});

test("Latin words and numbers inside keep their own direction", () => {
  assert.equal(visualRtl("צוות AI לעסקים"), "םיקסעל AI תווצ");
  assert.equal(visualRtl("14 ימים"), "םימי 14");
  assert.equal(visualRtl("(חינם)"), "(םניח)");
});
