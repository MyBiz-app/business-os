import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { palette } from "../src/index.ts";

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
const contrast = (a: string, b: string) => {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
};

test("text colors reach 4.5:1 on the background and the surface, in both themes", () => {
  for (const scheme of ["light", "dark"] as const) {
    const p = palette[scheme];
    for (const key of ["foreground", "muted", "primary", "ai", "success", "warning", "danger"] as const) {
      for (const on of [p.background, p.surface]) {
        assert.ok(contrast(p[key], on) >= 4.5, `${scheme} ${key} on ${on}: ${contrast(p[key], on).toFixed(2)}`);
      }
    }
    assert.ok(contrast(p.onPrimary, p.primary) >= 4.5, `${scheme} onPrimary`);
  }
});

test("the main colors match the web marketing palette", () => {
  const css = readFileSync(new URL("../../../apps/web/src/app/globals.css", import.meta.url), "utf8").toLowerCase();
  for (const hex of [palette.light.background, palette.light.foreground, palette.light.primary, palette.light.ai,
    palette.dark.background, palette.dark.surface, palette.dark.primary]) {
    assert.ok(css.includes(hex), `${hex} is not in globals.css`);
  }
});
