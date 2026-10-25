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
    for (const name of ["lead", "client", "quote", "invoice", "receipt", "session", "member", "service", "plan", "promo"]) {
      assert.ok(cards.has(name), name);
    }
  });

  it("opens clients, sessions and team members with ?open= (a dynamic intercepting route would also catch /clients/join, /schedule/closed and /team/shifts)", () => {
    const tenant = join(SRC, "app/(app)/(tenant)");
    for (const [page, window] of [
      ["clients/page.tsx", "ClientWindow"],
      ["schedule/page.tsx", "SessionWindow"],
      ["team/page.tsx", "StaffCardWindow"],
    ]) {
      const source = readFileSync(join(tenant, page), "utf8");
      assert.ok(source.includes(window) && source.includes("openedId"), page);
    }
    for (const folder of ["(.)clients", "(.)schedule"]) {
      assert.ok(!readdirSync(join(tenant, "@modal", folder)).includes("[id]"), `${folder} must not have a dynamic [id] window`);
    }
    assert.ok(!readdirSync(join(tenant, "@modal")).includes("(.)team"));
  });

  it("has an intercepted window route where the list links to an id with no static sibling", () => {
    const modal = join(SRC, "app/(app)/(tenant)/@modal");
    for (const route of ["(.)receipts/[id]", "(.)leads/[id]"]) {
      assert.ok(readFileSync(join(modal, route, "page.tsx"), "utf8").includes("transitionName"), route);
    }
  });

  it("needs no Next.js flag: ViewTransition works in the App Router as is", () => {
    const config = readFileSync(join(SRC, "..", "next.config.ts"), "utf8");
    assert.ok(!config.includes("viewTransition"));
  });
});

describe("soft page changes on the landing site", () => {
  it("softens the page at once on a click, listening in the capture phase (Next.js's Link has already prevented the default by the bubbling phase)", () => {
    const source = readFileSync(join(SRC, "components/ui/route-progress.tsx"), "utf8");
    assert.ok(source.includes('addEventListener("click", onClick, true)'));
    assert.ok(source.includes("dataset.navigating"));
  });

  it("has a page element to soften, and fades that last long enough not to read as a cut", () => {
    assert.ok(readFileSync(join(SRC, "app/(marketing)/template.tsx"), "utf8").includes("site-page"));
    const css = readFileSync(join(SRC, "app/globals.css"), "utf8");
    const duration = (rule: string) => Number(new RegExp(`${rule}\\)\\s*\\{\\s*animation:\\s*(\\d+)ms`).exec(css)?.[1]);
    assert.ok(duration("::view-transition-new\\(\\.vt-site-in") >= 300);
    assert.ok(duration("::view-transition-old\\(\\.vt-site-out") >= 150);
  });
});
