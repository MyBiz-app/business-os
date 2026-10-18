import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

const SRC = join(import.meta.dirname, "..");

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return files(path);
    return entry.name.endsWith(".tsx") ? [path] : [];
  });
}

/** Floating panels that open under a button. They are menus, not folds, so `CollapsibleSection`
 * (which pushes the content down) is the wrong tool. */
const POPOVERS = ["app/(app)/(tenant)/ai/chat-panel.tsx", "app/(app)/(tenant)/schedule/[id]/roster.tsx"];

describe("folding sections (R16, section 12 of the round 7 spec)", () => {
  it("uses CollapsibleSection instead of a bare <details>", () => {
    const found = files(SRC)
      .filter((file) => /<details[\s>]/.test(readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "")))
      .map((file) => relative(SRC, file))
      .sort();
    assert.deepEqual(found, [...POPOVERS].sort());
  });

  it("keeps the inline variant for a show-all, an add form and a danger zone", () => {
    const source = readFileSync(join(SRC, "components/ui/collapsible-section.tsx"), "utf8");
    assert.ok(source.includes('variant = "card"'));
    assert.ok(source.includes('variant === "inline"'));
    assert.ok(source.includes("aria-expanded"));
  });
});
