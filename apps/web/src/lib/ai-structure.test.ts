import assert from "node:assert/strict";
import { test } from "node:test";

import { connect, disconnect, draftOf, isCustom, payloadOf, removeTeam, setTeam, treeLayout, wouldCycle, type StructureAgent } from "./ai-structure.ts";

const agents: StructureAgent[] = [
  { key: "chief", state: "active" },
  { key: "a", state: "active" },
  { key: "b", state: "active" },
  { key: "c", state: "active" },
  { key: "locked", state: "locked" },
];

test("everyone starts under the chief and the shape is not custom", () => {
  const draft = draftOf(agents, []);
  assert.equal(draft.parents.a, "chief");
  assert.equal(isCustom(draft), false);
});

test("a line sets who reports to whom and loops are refused", () => {
  let draft = draftOf(agents, []);
  draft = connect(draft, agents, "b", "a");
  assert.equal(draft.parents.b, "a");
  assert.equal(isCustom(draft), true);
  assert.equal(wouldCycle(draft.parents, "a", "b"), true);
  assert.equal(connect(draft, agents, "a", "b"), draft);
  assert.equal(connect(draft, agents, "a", "a"), draft);
  assert.equal(connect(draft, agents, "chief", "a"), draft);
});

test("a locked agent cannot be connected, in either direction", () => {
  const draft = draftOf(agents, []);
  assert.equal(connect(draft, agents, "locked", "a"), draft);
  assert.equal(connect(draft, agents, "a", "locked"), draft);
});

test("removing a line sends the agent back to the chief", () => {
  const draft = disconnect(connect(draftOf(agents, []), agents, "b", "a"), "b");
  assert.equal(draft.parents.b, "chief");
});

test("the tree puts the chief on top and children below, parents centred", () => {
  const draft = connect(connect(draftOf(agents, []), agents, "b", "a"), agents, "c", "a");
  const spots = treeLayout(agents.slice(0, 4), draft.parents);
  const [chief, a, b, c] = ["chief", "a", "b", "c"].map((k) => spots.get(k)!);
  assert.ok(chief.y < a.y && a.y < b.y);
  assert.equal(b.y, c.y);
  assert.equal(a.x, (b.x + c.x) / 2);
});

test("a manual position wins over the tree", () => {
  const spots = treeLayout(agents.slice(0, 2), { a: "chief" }, { a: { x: 5, y: 95 } });
  assert.deepEqual(spots.get("a"), { x: 5, y: 95 });
});

test("teams: a lead leaves the team when the member moves out; removing a team frees its members", () => {
  let draft = draftOf(agents, [{ id: "t1", name: "T", color: "#000000", lead_key: "a" }]);
  draft = setTeam(draft, "a", "t1");
  draft = setTeam(draft, "a", null);
  assert.equal(draft.teams[0]!.lead_key, null);
  draft = removeTeam(setTeam(draft, "b", "t1"), "t1");
  assert.equal(draft.teamOf.b, null);
  assert.equal(draft.teams.length, 0);
});

test("the payload stores the default parent as nothing", () => {
  const draft = connect(draftOf(agents, []), agents, "b", "a");
  const sent = payloadOf(draft, agents);
  assert.equal(sent.agents.find((x) => x.key === "a")!.reports_to, null);
  assert.equal(sent.agents.find((x) => x.key === "b")!.reports_to, "a");
});
