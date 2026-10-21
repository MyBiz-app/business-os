import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { openedId, withOpen } from "./open-window.ts";

const ID = "61937869-cb75-4431-9f20-fe2f51def3e3";

describe("windows opened by a list page", () => {
  it("adds and removes ?open= and keeps the other filters", () => {
    assert.equal(withOpen("/clients", { q: "dana", status: "active" }, ID), `/clients?q=dana&status=active&open=${ID}`);
    assert.equal(withOpen("/clients", { q: "dana", open: ID }, null), "/clients?q=dana");
    assert.equal(withOpen("/clients", { open: ID }, null), "/clients");
    assert.equal(withOpen("/team", { tag: ["a", "b"] }, null), "/team?tag=a&tag=b");
  });

  it("opens a window only for something that looks like an id", () => {
    assert.equal(openedId({ open: ID }), ID);
    assert.equal(openedId({ open: "shifts" }), null);
    assert.equal(openedId({ open: ["x", ID] }), null);
    assert.equal(openedId({}), null);
  });
});
