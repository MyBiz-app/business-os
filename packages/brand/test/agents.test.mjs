import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { test } from "node:test";

import { ALL_AVATARS, DEFAULT_AGENTS, GALLERY_AVATARS, ILLUSTRATED_DEFAULTS } from "../src/agents.ts";

test("nine default agents, sixteen new gallery faces and the nine original illustrations, with distinct keys", () => {
  assert.equal(DEFAULT_AGENTS.length, 9);
  assert.equal(GALLERY_AVATARS.length, 16);
  assert.equal(ILLUSTRATED_DEFAULTS.length, 9);
  assert.equal(new Set(ALL_AVATARS.map((a) => a.key)).size, 25);
});

test("every avatar has its generated WebP and SVG", () => {
  for (const { key } of ALL_AVATARS) {
    for (const ext of ["webp", "svg"]) {
      assert.ok(existsSync(new URL(`../agents/${key}.${ext}`, import.meta.url)), `${key}.${ext} is missing: run build:agents`);
    }
  }
});

test("the nine agents use the plan's accent colors", () => {
  const colors = Object.fromEntries(DEFAULT_AGENTS.map((a) => [a.key, a.color]));
  assert.equal(colors.chief, "#7C3AED");
  assert.equal(colors.finance, "#10B981");
  assert.equal(colors.creative, "#F43F5E");
});
