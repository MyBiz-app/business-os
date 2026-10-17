import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

test("the copies of the brand file are in sync (fix: pnpm brand:sync)", () => {
  const script = fileURLToPath(new URL("../scripts/brand-sync.mjs", import.meta.url));
  const run = spawnSync("node", [script, "--check"], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
});
