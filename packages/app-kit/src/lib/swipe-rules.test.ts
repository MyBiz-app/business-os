import assert from "node:assert/strict";
import { test } from "node:test";

import { commits, isSideways, pullDistance, SWIPE_COMMIT } from "./swipe-rules.ts";

test("pullDistance follows the reading direction", () => {
  assert.equal(pullDistance(40, false), 40);
  assert.equal(pullDistance(-40, false), 0);
  assert.equal(pullDistance(-40, true), 40);
  assert.equal(pullDistance(40, true), 0);
});

test("pullDistance stops at the maximum pull", () => {
  assert.ok(pullDistance(1000, false) < SWIPE_COMMIT * 1.5);
});

test("isSideways ignores scrolling and tiny moves", () => {
  assert.equal(isSideways(30, 4), true);
  assert.equal(isSideways(30, 30), false);
  assert.equal(isSideways(5, 0), false);
});

test("commits at the commit distance", () => {
  assert.equal(commits(SWIPE_COMMIT - 1), false);
  assert.equal(commits(SWIPE_COMMIT), true);
});
