import assert from "node:assert/strict";
import { test } from "node:test";

import { agentForTab, initialOf, pickAgent } from "./ai-agents.ts";

const agents = [
  { key: "chief", state: "active" },
  { key: "marketing", state: "locked" },
  { key: "analyst", state: "active" },
];

test("each tab has its agent and everything else goes to the chief", () => {
  assert.equal(agentForTab("numbers"), "analyst");
  assert.equal(agentForTab("me"), "chief");
  assert.equal(agentForTab(undefined), "chief");
});

test("a locked agent is replaced by the chief", () => {
  assert.equal(pickAgent(agents, "marketing")?.key, "chief");
  assert.equal(pickAgent(agents, "analyst")?.key, "analyst");
});

test("without a chief the first usable agent opens", () => {
  assert.equal(pickAgent([{ key: "analyst", state: "active" }], "sales")?.key, "analyst");
  assert.equal(pickAgent([{ key: "analyst", state: "locked" }], "sales"), undefined);
});

test("the initial survives emoji and Hebrew", () => {
  assert.equal(initialOf(" אורי"), "א");
  assert.equal(initialOf("😀 Max"), "😀");
  assert.equal(initialOf(""), "?");
});
