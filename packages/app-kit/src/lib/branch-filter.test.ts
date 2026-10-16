import assert from "node:assert/strict";
import { test } from "node:test";

import { ALL_BRANCHES, branchKinds, filterByBranch, pickBranch, pickKind } from "./branch-filter.ts";

const branches = [
  { id: "a", name: "Center", kind: "strength" },
  { id: "b", name: "North", kind: "pilates" },
  { id: "c", name: "South", kind: "strength" },
  { id: "d", name: "Plain", kind: null },
];
const sessions = [{ location_id: "a" }, { location_id: "b" }, { location_id: "c" }, { location_id: null }];

test("kinds are unique, in order, without empty ones", () => {
  assert.deepEqual(branchKinds(branches), ["strength", "pilates"]);
});

test("no filter keeps every session", () => {
  assert.equal(filterByBranch(sessions, branches, ALL_BRANCHES).length, 4);
});

test("a branch filter keeps that branch only", () => {
  assert.deepEqual(filterByBranch(sessions, branches, pickBranch("b")), [{ location_id: "b" }]);
});

test("a kind filter keeps every branch of that kind", () => {
  assert.equal(filterByBranch(sessions, branches, pickKind(ALL_BRANCHES, "strength", branches)).length, 2);
});

test("picking a kind drops a branch of another kind", () => {
  assert.deepEqual(pickKind(pickBranch("b"), "strength", branches), { kind: "strength", branchId: null });
  assert.deepEqual(pickKind(pickBranch("a"), "strength", branches), { kind: "strength", branchId: "a" });
});

test("picking a branch clears the kind", () => {
  assert.deepEqual(pickBranch("a"), { branchId: "a", kind: null });
});
