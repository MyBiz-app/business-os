import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

const SRC = join(import.meta.dirname, "..");

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return files(path);
    return /\.tsx$/.test(entry.name) ? [path] : [];
  });
}

/** The name prefixes (`lead` in `lead-${id}`) used by a given prop across the web source. */
function prefixes(pattern: RegExp): Map<string, string[]> {
  const found = new Map<string, string[]>();
  for (const file of files(SRC)) {
    const source = readFileSync(file, "utf8");
    for (const match of source.matchAll(pattern)) {
      found.set(match[1], [...(found.get(match[1]) ?? []), file]);
    }
  }
  return found;
}

describe("card to window transitions (R29)", () => {
  const cards = prefixes(/<CardTransition\s+(?:key=\{[^}]+\}\s+)?name=\{`([a-z-]+)-\$\{/g);
  const windows = prefixes(/transitionName=\{`([a-z-]+)-\$\{/g);

  it("pairs every card in a list with the window opened from it, and the other way round", () => {
    for (const name of cards.keys()) assert.ok(windows.has(name), `card "${name}" has no window with the same name`);
    for (const name of windows.keys()) assert.ok(cards.has(name), `window "${name}" has no card with the same name`);
  });

  it("covers leads, clients, quotes, invoices, receipts, sessions and the catalog", () => {
    for (const name of ["lead", "client", "quote", "invoice", "receipt", "session", "service", "plan", "promo"]) {
      assert.ok(cards.has(name), name);
    }
  });

  it("has an intercepted window route for every list that links to a detail page", () => {
    const modal = join(SRC, "app/(app)/(tenant)/@modal");
    for (const route of ["(.)clients/[id]", "(.)schedule/[id]", "(.)receipts/[id]", "(.)leads/[id]"]) {
      assert.ok(readFileSync(join(modal, route, "page.tsx"), "utf8").includes("transitionName"), route);
    }
  });

  it("needs no Next.js flag: ViewTransition works in the App Router as is", () => {
    const config = readFileSync(join(SRC, "..", "next.config.ts"), "utf8");
    assert.ok(!config.includes("viewTransition"));
  });
});
