import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { anchorOf, matchArea, matchQueryChild, pathOf, sectionAnchors } from "./nav-match.ts";

const items = [
  { href: "/clients", children: [{ href: "/clients" }, { href: "/clients/join" }, { href: "/clients/import" }] },
  { href: "/catalog", children: [{ href: "/catalog?tab=services" }, { href: "/catalog?tab=plans" }] },
  { href: "/ai", children: [{ href: "/ai#ai-team" }, { href: "/ai#ai-tasks" }] },
  { href: "/sales", children: [{ href: "/sales" }, { href: "/sales/orders" }] },
  { href: "/files" },
];

describe("side menu matching (R12)", () => {
  it("picks the most specific address and lets a sub-page win a tie with its area", () => {
    assert.equal(matchArea(items, "/clients/join")?.href, "/clients/join");
    assert.equal(matchArea(items, "/clients/join")?.child, true);
    assert.equal(matchArea(items, "/clients")?.child, true, "the list is a sub-item of its own area");
    assert.equal(matchArea(items, "/clients/abc")?.item.href, "/clients");
    assert.equal(matchArea(items, "/sales/orders")?.href, "/sales/orders");
    assert.equal(matchArea(items, "/files/x")?.child, false);
    assert.equal(matchArea(items, "/nowhere"), undefined);
  });

  it("does not mistake a longer name for a sub-page (/files vs /files-archive)", () => {
    assert.equal(matchArea(items, "/files-archive"), undefined);
  });

  it("section links never match a page", () => {
    assert.equal(matchArea(items, "/ai")?.child, false);
  });

  it("chooses the tab named in the address, else the first", () => {
    const kids = items[1].children ?? [];
    assert.equal(matchQueryChild(kids, "/catalog", "plans"), "/catalog?tab=plans");
    assert.equal(matchQueryChild(kids, "/catalog", null), "/catalog?tab=services");
    assert.equal(matchQueryChild(kids, "/catalog", "unknown"), "/catalog?tab=services");
    assert.equal(matchQueryChild(kids, "/clients", "plans"), null);
  });

  it("lists the sections of the open page only", () => {
    assert.deepEqual(sectionAnchors(items[2].children ?? [], "/ai"), ["ai-team", "ai-tasks"]);
    assert.deepEqual(sectionAnchors(items[2].children ?? [], "/clients"), []);
    assert.equal(pathOf("/ai#ai-team"), "/ai");
    assert.equal(anchorOf("/ai#ai-team"), "ai-team");
    assert.equal(anchorOf("/ai"), null);
  });

  it("every section link in the menu points at an element that exists on its page", () => {
    const dir = join(import.meta.dirname, "..", "app/(app)/(tenant)");
    const menu = readFileSync(join(dir, "crm-frame.tsx"), "utf8");
    const links = [...menu.matchAll(/href: "(\/[a-z-]+)#([a-z-]+)"/g)];
    assert.ok(links.length >= 2);
    for (const [, path, id] of links) {
      const folder = join(dir, path.slice(1));
      const sources = readdirSync(folder).filter((f) => f.endsWith(".tsx")).map((f) => readFileSync(join(folder, f), "utf8"));
      assert.ok(sources.some((source) => source.includes(`id="${id}"`)), `${path}#${id} has no element with that id`);
    }
  });
});
