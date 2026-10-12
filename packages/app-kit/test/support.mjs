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
