import assert from "node:assert/strict";
import { test } from "node:test";

import { rememberedIn } from "./remembered-core.ts";

const broken = {
  getItem: () => Promise.reject(new Error("storage full")),
  setItem: () => Promise.reject(new Error("storage full")),
};

test("a failing read is nothing remembered, and a failing write is skipped", async () => {
  const store = rememberedIn(broken);
  assert.equal(await store.read("client.business"), null);
  assert.equal(await store.write("client.business", "x"), undefined);
});

test("a working storage is passed through", async () => {
  const data = new Map<string, string>();
  const store = rememberedIn({
    getItem: async (key) => data.get(key) ?? null,
    setItem: async (key, value) => void data.set(key, value),
  });
  await store.write("a", "1");
  assert.equal(await store.read("a"), "1");
  assert.equal(await store.read("b"), null);
});
