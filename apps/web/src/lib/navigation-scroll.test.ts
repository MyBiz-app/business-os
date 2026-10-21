import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { planNavigation } from "./navigation-scroll.ts";

const base = { pathname: "/team/shifts", previous: "/team", hash: "", traversal: false, saved: undefined, windowOpen: false, under: null };

describe("scroll after a page change", () => {
  it("starts a new page at the top", () => {
    assert.deepEqual(planNavigation(base), { plan: { kind: "top" }, under: null });
  });

  it("goes to the section named in the address", () => {
    assert.deepEqual(planNavigation({ ...base, hash: "#ai-tasks" }).plan, { kind: "anchor", id: "ai-tasks" });
    assert.deepEqual(planNavigation({ ...base, hash: "#%D7%A6%D7%95%D7%95%D7%AA" }).plan, { kind: "anchor", id: "צוות" });
  });

  it("back and forward return to where the person was", () => {
    assert.deepEqual(planNavigation({ ...base, traversal: true, saved: 640 }).plan, { kind: "restore", y: 640 });
    assert.deepEqual(planNavigation({ ...base, traversal: true }).plan, { kind: "top" });
  });

  it("a window over the page keeps the page, and so does closing it", () => {
    const opened = planNavigation({ ...base, pathname: "/clients/7", previous: "/clients", windowOpen: true });
    assert.deepEqual(opened, { plan: { kind: "keep" }, under: "/clients" });
    const next = planNavigation({ ...base, pathname: "/clients/8", previous: "/clients/7", windowOpen: true, under: opened.under });
    assert.equal(next.under, "/clients");
    const closed = planNavigation({ ...base, pathname: "/clients", previous: "/clients/7", under: opened.under });
    assert.deepEqual(closed, { plan: { kind: "keep" }, under: null });
  });

  it("leaving a window for a different page starts at the top", () => {
    assert.deepEqual(planNavigation({ ...base, pathname: "/invoices/3", previous: "/clients/7", under: "/clients" }), { plan: { kind: "top" }, under: null });
  });
});
