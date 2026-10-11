import assert from "node:assert/strict";
import { test } from "node:test";

import { newIdempotencyKey } from "./idempotency.ts";

test("keys are long enough for the API and never repeat", () => {
  const keys = new Set(Array.from({ length: 1000 }, () => newIdempotencyKey()));
  assert.equal(keys.size, 1000);
  for (const key of keys) assert.ok(key.length >= 8 && key.length <= 80, key);
});
