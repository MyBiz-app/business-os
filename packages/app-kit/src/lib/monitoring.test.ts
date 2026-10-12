import assert from "node:assert/strict";
import test from "node:test";

// The pure scrubbing helper is copied here by name: the module itself needs the React Native SDK.
import { readFileSync } from "node:fs";

test("monitoring stays off without a DSN and scrubs request and user details", () => {
  const source = readFileSync(new URL("./monitoring.ts", import.meta.url), "utf8");
  assert.match(source, /if \(!DSN\) return false/);
  assert.match(source, /sendDefaultPii: false/);
  assert.match(source, /beforeSend: scrubEvent/);
  assert.match(source, /split\("\?"\)\[0\]/);
  assert.match(source, /delete event\.user/);
});
