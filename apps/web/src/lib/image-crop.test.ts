import assert from "node:assert/strict";
import { test } from "node:test";

import { clampView, cropSquare, croppedName, zoomTo } from "./image-crop.ts";

test("at zoom 1 a landscape picture shows its middle square", () => {
  const { sx, sy, side } = cropSquare({ zoom: 1, x: 0, y: 0 }, 400, 200, 100);
  assert.deepEqual([sx, sy, side], [100, 0, 200]);
});

test("the picture cannot be dragged away from the box", () => {
  // 400x200 in a 100 box at zoom 1: scale 0.5, shown 200x100, so it can move 50px sideways only.
  assert.deepEqual(clampView({ zoom: 1, x: 500, y: 500 }, 400, 200, 100), { zoom: 1, x: 50, y: 0 });
  const { sx } = cropSquare({ zoom: 1, x: 500, y: 0 }, 400, 200, 100);
  assert.equal(sx, 0);
});

test("zoom stays within its limits", () => {
  assert.equal(clampView({ zoom: 99, x: 0, y: 0 }, 200, 200, 100).zoom, 4);
  assert.equal(clampView({ zoom: 0.1, x: 0, y: 0 }, 200, 200, 100).zoom, 1);
});

test("zooming in keeps the same point in the middle", () => {
  const view = zoomTo({ zoom: 2, x: 20, y: -10 }, 4, 200, 200, 100);
  assert.deepEqual([view.zoom, view.x, view.y], [4, 40, -20]);
  assert.equal(cropSquare(view, 200, 200, 100).side, 50);
});

test("the cropped file keeps its name with the new extension", () => {
  assert.equal(croppedName("me.final.jpeg", "image/webp"), "me.final.webp");
  assert.equal(croppedName("logo", "image/png"), "logo.png");
});
