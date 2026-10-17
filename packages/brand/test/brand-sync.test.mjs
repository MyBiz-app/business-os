import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

test("the copies of the brand file are in sync (fix: pnpm brand:sync)", () => {
  const script = fileURLToPath(new URL("../scripts/brand-sync.mjs", import.meta.url));
  const run = spawnSync("node", [script, "--check"], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
});

test("the web app's cookie names use the cookie prefix of the brand file", () => {
  const prefix = JSON.parse(readFileSync(new URL("../../i18n/brand.json", import.meta.url), "utf8")).app.cookiePrefix;
  const mfa = readFileSync(new URL("../../../apps/web/src/lib/mfa.ts", import.meta.url), "utf8");
  assert.ok(mfa.includes(`ACTIVITY_COOKIE = "${prefix}_active"`));
  assert.ok(mfa.includes(`DEVICE_COOKIE = "${prefix}_device"`));
});
