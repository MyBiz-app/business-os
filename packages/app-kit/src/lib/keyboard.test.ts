import assert from "node:assert/strict";
import { test } from "node:test";

import { coveredHeight, revealDelta } from "./keyboard.ts";

test("a field under the keyboard scrolls up by what hides it plus the margin", () => {
  assert.equal(revealDelta({ inputBottom: 700, keyboardTop: 560, margin: 24 }), 164);
});

test("a field that is already visible does not move the screen", () => {
  assert.equal(revealDelta({ inputBottom: 300, keyboardTop: 560, margin: 24 }), 0);
  assert.equal(revealDelta({ inputBottom: 536, keyboardTop: 560, margin: 24 }), 0);
});

test("the covered height is what is below the top of the keyboard, never negative", () => {
  assert.equal(coveredHeight(560, 852), 292);
  assert.equal(coveredHeight(900, 852), 0);
});
