import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

const SRC = join(import.meta.dirname, "..");

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return files(path);
    return /\.tsx?$/.test(entry.name) && !entry.name.endsWith(".test.ts") ? [path] : [];
  });
}

describe("windows (CRM Premium, slice W1-2)", () => {
  it("asks with ConfirmDialog, never with the browser's grey box", () => {
    const found = files(SRC)
      .filter((file) => /\bwindow\.(confirm|alert|prompt)\(/.test(readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "")))
      .map((file) => relative(SRC, file))
      .sort();
    assert.deepEqual(found, []);
  });
});
