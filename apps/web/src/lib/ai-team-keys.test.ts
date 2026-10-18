import assert from "node:assert/strict";
import { test } from "node:test";

import { agentForIndustry, SPECIALISTS } from "./ai-team-keys.ts";

test("every industry gets a specialist, defaulting to the secretary", () => {
  assert.equal(agentForIndustry("fitness"), "secretary");
  assert.equal(agentForIndustry("food"), "care");
  assert.ok(SPECIALISTS.includes(agentForIndustry("anything-new")));
});
