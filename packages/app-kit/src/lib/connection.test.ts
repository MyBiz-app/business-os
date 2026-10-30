import assert from "node:assert/strict";
import test from "node:test";

import { isNetworkFailure, isOnline, setOnline } from "./connection.ts";

test("the connection state flips once and tells listeners only about changes", () => {
  assert.equal(isOnline(), true);
  setOnline(false);
  assert.equal(isOnline(), false);
  setOnline(true);
  assert.equal(isOnline(), true);
});

test("a failed fetch counts as no connection; a cancelled one does not", () => {
  assert.equal(isNetworkFailure(new TypeError("Network request failed")), true);
  assert.equal(isNetworkFailure(new Error("Failed to fetch")), true);
  assert.equal(isNetworkFailure(new DOMException("aborted", "AbortError")), false);
  assert.equal(isNetworkFailure(new Error("API 409: conflict")), false);
});
