import assert from "node:assert/strict";
import { test } from "node:test";

import { agentForPath, bubbleHidden, fanFor } from "./ai-bubble.ts";

test("each screen maps to its agent, the chief elsewhere", () => {
  assert.equal(agentForPath("/leads"), "marketing");
  assert.equal(agentForPath("/messages/abc"), "marketing");
  assert.equal(agentForPath("/schedule"), "secretary");
  assert.equal(agentForPath("/quotes"), "sales");
  assert.equal(agentForPath("/bills"), "finance");
  assert.equal(agentForPath("/team"), "team");
  assert.equal(agentForPath("/dashboard"), "analyst");
  assert.equal(agentForPath("/settings"), "chief");
  assert.equal(agentForPath("/teams-other"), "chief");
});

test("the bubble hides on the AI team and its redirect", () => {
  assert.equal(bubbleHidden("/ai"), true);
  assert.equal(bubbleHidden("/ai/x"), true);
  assert.equal(bubbleHidden("/assistant"), true);
  assert.equal(bubbleHidden("/aim"), false);
  assert.equal(bubbleHidden("/leads"), false);
});

test("the fan starts with the chief and the screen's agent and skips unavailable ones", () => {
  const all = ["chief", "secretary", "marketing", "sales", "finance", "team"];
  assert.deepEqual(fanFor("/leads", all), ["chief", "marketing", "secretary", "sales", "finance"]);
  assert.deepEqual(fanFor("/team", all), ["chief", "team", "secretary", "marketing", "sales"]);
  assert.deepEqual(fanFor("/leads", ["chief", "sales"]), ["chief", "sales"]);
});
