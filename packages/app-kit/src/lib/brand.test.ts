import assert from "node:assert/strict";
import { test } from "node:test";

import { brandPalette } from "./brand.ts";
import { colors } from "./theme.ts";

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
const contrast = (a: string, b: string) => {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
};

// Brand colors businesses pick, including the mid-tones that used to fail in dark mode.
const SAMPLES = ["#4f46e5", "#0f766e", "#7c3aed", "#b45309", "#e11d48", "#fde047", "#22d3ee", "#000000", "#ffffff"];

test("a brand color stays readable on the surface and under its own button text", () => {
  for (const scheme of ["light", "dark"] as const) {
    for (const color of SAMPLES) {
      const palette = brandPalette(colors[scheme], color);
      assert.ok(contrast(palette.primary, palette.surface) >= 4.5, `${color} on ${scheme} surface`);
      assert.ok(contrast(palette.primary, palette.onPrimary) >= 4.5, `text on ${color} (${scheme})`);
    }
  }
});
