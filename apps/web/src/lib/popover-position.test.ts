import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { computePopoverPosition } from "./popover-position.ts";

const viewport = { width: 1000, height: 700 };
const panel = { width: 200, height: 160 };
const at = (left: number, top: number): { left: number; top: number; width: number; height: number } => ({ left, top, width: 40, height: 36 });

describe("computePopoverPosition", () => {
  it("opens below, aligned to the start edge in English", () => {
    const result = computePopoverPosition({ anchor: at(300, 100), panel, viewport });
    assert.deepEqual(result, { left: 300, top: 144, placement: "bottom-start" });
  });

  it("aligns the start edge to the right edge of the anchor in Hebrew", () => {
    const result = computePopoverPosition({ anchor: at(300, 100), panel, viewport, rtl: true });
    assert.equal(result.left, 300 + 40 - 200);
  });

  it("end alignment is the opposite edge", () => {
    assert.equal(computePopoverPosition({ anchor: at(300, 100), panel, viewport, placement: "bottom-end" }).left, 140);
    assert.equal(computePopoverPosition({ anchor: at(300, 100), panel, viewport, placement: "bottom-end", rtl: true }).left, 300);
  });

  it("flips above when there is no room below but there is above", () => {
    const result = computePopoverPosition({ anchor: at(300, 600), panel, viewport });
    assert.equal(result.placement, "top-start");
    assert.equal(result.top, 600 - 8 - 160);
  });

  it("stays below when it fits on neither side", () => {
    const small = { width: 1000, height: 200 };
    const result = computePopoverPosition({ anchor: at(300, 80), panel, viewport: small });
    assert.equal(result.placement, "bottom-start");
  });

  it("prefers top and flips down when the top has no room", () => {
    const result = computePopoverPosition({ anchor: at(300, 50), panel, viewport, placement: "top-start" });
    assert.equal(result.placement, "bottom-start");
  });

  it("keeps the panel inside the viewport sideways", () => {
    assert.equal(computePopoverPosition({ anchor: at(980, 100), panel, viewport }).left, 1000 - 8 - 200);
    assert.equal(computePopoverPosition({ anchor: at(-30, 100), panel, viewport }).left, 8);
  });
});
