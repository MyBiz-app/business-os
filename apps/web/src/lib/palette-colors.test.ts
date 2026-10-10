import assert from "node:assert/strict";
import { test } from "node:test";

import { contrast, deriveTheme, type PaletteColors } from "./palette-colors.ts";

function check(colors: PaletteColors) {
  const { tokens } = deriveTheme(colors);
  const bg = tokens["--background"];
  const surface = tokens["--surface"];
  assert.ok(contrast(tokens["--foreground"], bg) >= 7, "text on page");
  assert.ok(contrast(tokens["--foreground"], surface) >= 7, "text on cards");
  assert.ok(contrast(tokens["--muted"], bg) >= 4.5, "secondary text");
  assert.ok(contrast(tokens["--muted"], surface) >= 4.5, "secondary text on cards");
  assert.ok(contrast(tokens["--primary"], bg) >= 4.5, "accent on page");
  assert.ok(contrast(tokens["--on-primary"], tokens["--primary"]) >= 4.5, "text on buttons");
  for (const name of ["--success", "--danger", "--warning"]) assert.ok(contrast(tokens[name], bg) >= 4.5, name);
  assert.notEqual(surface, bg);
  assert.notEqual(tokens["--border"], bg);
}

test("the default colors pass untouched", () => {
  const theme = deriveTheme({ background: "#ffffff", text: "#0a0a0a", accent: "#6d28d9" });
  assert.equal(theme.scheme, "light");
  assert.deepEqual(theme.adjusted, { background: false, text: false, accent: false });
  check({ background: "#ffffff", text: "#0a0a0a", accent: "#6d28d9" });
});

test("everything black still gives a readable screen", () => {
  const colors = { background: "#000000", text: "#000000", accent: "#000000" };
  const theme = deriveTheme(colors);
  assert.equal(theme.scheme, "dark");
  assert.deepEqual(theme.adjusted, { background: false, text: true, accent: true });
  check(colors);
});

test("the same color three times, and other awkward picks, stay readable", () => {
  for (const hex of ["#ffffff", "#808080", "#ff00ff", "#ffff00", "#0000ff", "#7f7f7f"]) check({ background: hex, text: hex, accent: hex });
  check({ background: "#ffeb3b", text: "#fff176", accent: "#fdd835" });
  check({ background: "#1a237e", text: "#283593", accent: "#303f9f" });
});

test("invalid colors fall back to the defaults", () => {
  const theme = deriveTheme({ background: "red", text: "", accent: "#12" });
  assert.equal(theme.tokens["--background"], "#ffffff");
  check({ background: "red", text: "", accent: "#12" });
});

test("a dark background gives the dark scheme", () => {
  assert.equal(deriveTheme({ background: "#101820", text: "#f0f0f0", accent: "#22d3ee" }).scheme, "dark");
});
