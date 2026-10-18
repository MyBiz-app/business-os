import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { share } from "../components/branch-map/map-core.ts";

describe("share (marker size on the branches map)", () => {
  it("is the ratio to the largest branch", () => {
    assert.equal(share(50, [100, 50, null]), 0.5);
    assert.equal(share(100, [100, 50, null]), 1);
  });

  it("is 0 for a missing or empty value and when no branch has numbers", () => {
    assert.equal(share(null, [100]), 0);
    assert.equal(share(0, [100]), 0);
    assert.equal(share(5, [null, 0]), 0);
    assert.equal(share(null, []), 0);
  });
});
