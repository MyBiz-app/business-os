import assert from "node:assert/strict";
import { test } from "node:test";

import { usageWarnings } from "../src/usage.ts";

const usage = (messages: number, storage: number) => ({
  messages,
  messages_included: 200,
  storage_bytes: storage,
  storage_included_bytes: 1000,
});

test("nothing below 80% of the bundle", () => {
  assert.deepEqual(usageWarnings(usage(159, 799)), []);
});

test("near from 80%, over from 100%", () => {
  assert.deepEqual(usageWarnings(usage(160, 1000)), [
    { key: "nearMessages", percent: 80 },
    { key: "overStorage", percent: 100 },
  ]);
  assert.deepEqual(usageWarnings(usage(250, 0)), [{ key: "overMessages", percent: 125 }]);
});

test("AI allowance warns like the others, and is skipped without an AI module", () => {
  const base = { messages: 0, messages_included: 200, storage_bytes: 0, storage_included_bytes: 1000 };
  assert.deepEqual(usageWarnings({ ...base, ai_credits: 320, ai_credits_included: 400 }), [{ key: "nearAi", percent: 80 }]);
  assert.deepEqual(usageWarnings({ ...base, ai_credits: 400, ai_credits_included: 400 }), [{ key: "overAi", percent: 100 }]);
  assert.deepEqual(usageWarnings({ ...base, ai_credits: 0, ai_credits_included: 0 }), []);
});
