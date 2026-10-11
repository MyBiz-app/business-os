import assert from "node:assert/strict";
import { test } from "node:test";

import { createChunkedStorage, type KeyValueBackend } from "./chunked-storage.ts";

function memory(): KeyValueBackend & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: async (key) => data.get(key) ?? null,
    setItem: async (key, value) => void data.set(key, value),
    removeItem: async (key) => void data.delete(key),
  };
}

test("round-trips a value larger than one chunk", async () => {
  const backend = memory();
  const storage = createChunkedStorage(backend, undefined, 10);
  const value = "x".repeat(35);
  await storage.setItem("k", value);
  assert.equal(await storage.getItem("k"), value);
  assert.ok([...backend.data.values()].every((v) => v.length <= 10));
});

test("overwriting with a shorter value leaves no stale chunks", async () => {
  const backend = memory();
  const storage = createChunkedStorage(backend, undefined, 5);
  await storage.setItem("k", "a".repeat(20));
  await storage.setItem("k", "b".repeat(6));
  assert.equal(await storage.getItem("k"), "b".repeat(6));
  assert.equal(backend.data.size, 3);
});

test("removeItem clears every piece", async () => {
  const backend = memory();
  const storage = createChunkedStorage(backend, undefined, 5);
  await storage.setItem("k", "a".repeat(20));
  await storage.removeItem("k");
  assert.equal(backend.data.size, 0);
  assert.equal(await storage.getItem("k"), null);
});

test("a missing chunk reads as signed out", async () => {
  const backend = memory();
  const storage = createChunkedStorage(backend, undefined, 5);
  await storage.setItem("k", "a".repeat(20));
  backend.data.delete("k.2");
  assert.equal(await storage.getItem("k"), null);
});

test("moves a session saved in the old storage over to the secure one", async () => {
  const secure = memory();
  const old = memory();
  old.data.set("k", "legacy-session");
  const storage = createChunkedStorage(secure, old, 5);
  assert.equal(await storage.getItem("k"), "legacy-session");
  assert.equal(old.data.size, 0);
  assert.equal(await storage.getItem("k"), "legacy-session");
});
