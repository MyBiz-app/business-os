import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { fontSizes, palette, radius, space, typeScale } from "../src/index.ts";

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
    for (const key of ["foreground", "muted", "primaryInk", "ai", "success", "warning", "danger"] as const) {
      for (const on of [p.background, p.surface]) {
        assert.ok(contrast(p[key], on) >= 4.5, `${scheme} ${key} on ${on}: ${contrast(p[key], on).toFixed(2)}`);
      }
    }
    assert.ok(contrast(p.onPrimary, p.primary) >= 4.5, `${scheme} onPrimary`);
  }
});

/** The declarations of the first `selector { ... }` block in globals.css, as custom property -> value. */
function cssBlock(css: string, selector: string): Record<string, string> {
  const start = css.indexOf(`\n${selector} {`);
  assert.ok(start >= 0, `${selector} block not found in globals.css`);
  const body = css.slice(css.indexOf("{", start) + 1, css.indexOf("\n}", start));
  const vars: Record<string, string> = {};
  for (const [, name, value] of body.matchAll(/(--[a-z-]+):\s*([^;]+);/g)) vars[name] = value.trim().toLowerCase();
  return vars;
}

test("the palette is the web's Calm palette, token by token", () => {
  const css = readFileSync(new URL("../../../apps/web/src/app/globals.css", import.meta.url), "utf8");
  // palette key -> the CSS custom property it mirrors (the same value in light and dark).
  const mirrored: Record<string, string> = {
    background: "--background",
    foreground: "--foreground",
    surface: "--surface",
    subtle: "--subtle",
    border: "--border",
    muted: "--muted",
    primary: "--palette-primary",
    primaryInk: "--palette-primary-ink",
    onPrimary: "--palette-on-primary",
    successInk: "--success-ink",
    warning: "--warning",
    danger: "--danger",
    onDanger: "--on-danger",
    successSoft: "--success-soft",
    warningSoft: "--warning-soft",
    dangerSoft: "--danger-soft",
    infoSoft: "--info-soft",
    infoInk: "--info-ink",
  };
  for (const [scheme, selector] of [["light", ":root"], ["dark", ".dark"]] as const) {
    // `.dark` only overrides what changes at night: fall back to the light value for the rest.
    const vars = { ...cssBlock(css, ":root"), ...cssBlock(css, selector) };
    for (const [key, cssName] of Object.entries(mirrored)) {
      assert.equal(palette[scheme][key as keyof (typeof palette)["light"]], vars[cssName], `${scheme} ${key} vs ${cssName}`);
    }
  }
});

test("type sizes, corners and spacing follow the Apple scale", () => {
  assert.deepEqual(fontSizes, [12, 13, 15, 16, 17, 20, 22, 28, 34]);
  for (const entry of Object.values(typeScale)) assert.ok(fontSizes.includes(entry.size), `${entry.size} is not on the scale`);
  assert.deepEqual([radius.control, radius.card, radius.dialog], [10, 12, 16]);
  for (const step of Object.values(space)) assert.equal(step % 4, 0, `${step} is not on the 4px grid`);
});
