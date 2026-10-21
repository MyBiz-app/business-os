import assert from "node:assert/strict";
import { test } from "node:test";

import { agentForPath, bubbleHidden, fanFor } from "./ai-bubble.ts";

const team = [
  { key: "chief", routes: ["/dashboard", "/settings", "/files"] },
  { key: "secretary", routes: ["/schedule", "/clients"] },
  { key: "marketing", routes: ["/leads"] },
  { key: "sales", routes: ["/quotes"] },
  { key: "finance", routes: ["/bills"] },
  { key: "care", routes: ["/messages"] },
  { key: "team", routes: ["/team", "/team/payroll"] },
];

test("each screen maps to the agent that lists it, the chief elsewhere", () => {
  assert.equal(agentForPath("/leads", team), "marketing");
  assert.equal(agentForPath("/messages/abc", team), "care");
  assert.equal(agentForPath("/quotes", team), "sales");
  assert.equal(agentForPath("/files", team), "chief");
  assert.equal(agentForPath("/nowhere", team), "chief");
  assert.equal(agentForPath("/teams-other", team), "chief");
});

test("the bubble hides on the AI team and its redirect", () => {
  assert.equal(bubbleHidden("/ai"), true);
  assert.equal(bubbleHidden("/ai/x"), true);
  assert.equal(bubbleHidden("/assistant"), true);
  assert.equal(bubbleHidden("/aim"), false);
  assert.equal(bubbleHidden("/leads"), false);
});

test("the fan never repeats the agent on the round button and fills up to five", () => {
  assert.deepEqual(fanFor("/leads", team, "marketing"), ["chief", "secretary", "sales", "finance", "care"]);
  assert.deepEqual(fanFor("/dashboard", team, "chief"), ["secretary", "marketing", "sales", "finance", "care"]);
  assert.deepEqual(fanFor("/leads", team.slice(0, 1), "chief"), []);
});

test("the screen's agent comes first when someone else is on the button", () => {
  assert.deepEqual(fanFor("/leads", team, "chief").slice(0, 2), ["marketing", "secretary"]);
});
