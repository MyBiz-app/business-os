import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { composeInstructions, MAX_INSTRUCTIONS, TEMPLATES, TOOL_DOMAINS } from "./agent-templates.ts";

const labels = { does: "Does:", never: "Never:", knowledge: "Knows:" };

describe("composeInstructions", () => {
  it("labels the filled boxes and skips the empty ones", () => {
    assert.equal(composeInstructions({ does: " Answer questions ", never: "", knowledge: "Open 9 to 5" }, labels), "Does:\nAnswer questions\n\nKnows:\nOpen 9 to 5");
  });

  it("stays within what the API accepts", () => {
    assert.equal(composeInstructions({ does: "x".repeat(MAX_INSTRUCTIONS + 50), never: "", knowledge: "" }, labels).length, MAX_INSTRUCTIONS);
  });
});

describe("TEMPLATES", () => {
  it("only use tool domains a custom agent can have", () => {
    for (const template of TEMPLATES) for (const domain of template.domains) assert.ok((TOOL_DOMAINS as readonly string[]).includes(domain), domain);
  });
});
