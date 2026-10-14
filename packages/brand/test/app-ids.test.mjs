import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const ids = JSON.parse(readFileSync(new URL("../app-ids.json", import.meta.url), "utf8"));

test("every app has a distinct, valid store id", () => {
  const values = Object.values(ids);
  assert.deepEqual(Object.keys(ids).sort(), ["client"]);
  assert.equal(new Set(values).size, values.length);
  for (const id of values) assert.match(id, /^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*){2,}$/);
});

test("the Expo apps take their ids from the shared file, not from app.json", () => {
  for (const [app, key] of [["client-app", "client"]]) {
    const json = JSON.parse(readFileSync(new URL(`../../../apps/${app}/app.json`, import.meta.url), "utf8"));
    assert.equal(json.expo.ios.bundleIdentifier, undefined);
    assert.equal(json.expo.android.package, undefined);
    const config = readFileSync(new URL(`../../../apps/${app}/app.config.js`, import.meta.url), "utf8");
    assert.ok(config.includes(`ids.${key}`));
  }
});
