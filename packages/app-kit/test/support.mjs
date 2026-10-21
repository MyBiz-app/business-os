// Checks shared by the three Expo apps and app-kit: what a typecheck can't see.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { test } from "node:test";

const MESSAGES = new URL("../../i18n/messages/", import.meta.url);

function sourceFiles(dir) {
  return readdirSync(dir, { withFileTypes: true, recursive: true })
    .filter((entry) => entry.isFile() && /\.tsx?$/.test(entry.name) && !/\.test\./.test(entry.name))
    .map((entry) => join(entry.parentPath, entry.name));
}

function messages(locale) {
  return JSON.parse(readFileSync(new URL(`${locale}.json`, MESSAGES), "utf8"));
}

/** Registers the checks for a source folder; `routes` is the app's expo-router folder, if any. */
export function checkSources(root, { routes } = {}) {
  const files = sourceFiles(root);

  // The Calm scale (packages/design-tokens): a screen takes its sizes and corners from it, so the app
  // and the web look like one product. Computed values (an avatar's initials, a circle) are not literals.
  test("font sizes, weights and corners come from the Calm scale", () => {
    const sizes = new Set([12, 13, 15, 17, 20, 24, 30]);
    const offScale = [];
    for (const file of files) {
      // The launch splash draws the logo mark with the logo's own geometry, not interface.
      if (file.endsWith("launch-splash.tsx")) continue;
      const code = readFileSync(file, "utf8");
      const where = (index) => `${relative(root, file)}:${code.slice(0, index).split("\n").length}`;
      for (const m of code.matchAll(/fontSize: (\d+(?:\.\d+)?)\b(?!\s*[*/])/g)) {
        // 1px is the OTP input's hidden field; it is never drawn.
        if (!sizes.has(Number(m[1])) && m[1] !== "1") offScale.push(`${where(m.index)} fontSize ${m[1]}`);
      }
      for (const m of code.matchAll(/fontWeight: "(700|800|900|bold)"/g)) offScale.push(`${where(m.index)} fontWeight ${m[1]} (headings are 600)`);
      // Corners 8 and up are tokens (radius.control, radius.card, radius.dialog, radius.pill); small marks may be literals.
      for (const m of code.matchAll(/border(?:Top|Bottom)?(?:Start|End|Left|Right)?Radius: (\d+)\b(?!\s*[*/])/g)) {
        if (Number(m[1]) > 7) offScale.push(`${where(m.index)} borderRadius ${m[1]}`);
      }
    }
    assert.deepEqual(offScale, []);
  });

  test("every message namespace a screen asks for exists in both languages", () => {
    const missing = [];
    for (const file of files) {
      const code = readFileSync(file, "utf8");
      for (const [, namespace] of code.matchAll(/useTranslations\(\s*"([^"]+)"\s*\)/g)) {
        for (const locale of ["en", "he"]) {
          const node = namespace.split(".").reduce((n, part) => n?.[part], messages(locale));
          if (typeof node !== "object" || node === null) {
            missing.push(`${relative(root, file)}: "${namespace}" is missing from ${locale}.json`);
          }
        }
      }
    }
    assert.deepEqual(missing, []);
  });

  if (routes) {
    test("every route file exports a default screen", () => {
      const broken = sourceFiles(routes)
        .filter((file) => !/export default |as default/.test(readFileSync(file, "utf8")))
        .map((file) => relative(routes, file));
      assert.deepEqual(broken, []);
    });
  }
}
