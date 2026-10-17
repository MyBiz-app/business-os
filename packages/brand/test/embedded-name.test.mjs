// The product's name has one home, packages/i18n/brand.json. This fails when code spells it out
// somewhere else, so renaming the product stays a change to that one file (docs/brand-rename.md).
// Comments and docstrings may say "MyBiz"; so may tests, docs and translation files (which are
// written with the name and swapped at build time, see packages/i18n/src/brand.ts).
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../../", import.meta.url));

/** Files that may spell the name, each with the reason. */
const ALLOWED = new Map([
  ["packages/i18n/brand.json", "the one brand file"],
  ["apps/api/app/core/brand.json", "generated copy of the brand file (pnpm brand:sync)"],
  ["packages/i18n/src/brand.ts", "WRITTEN: how the translations spell the name before the swap"],
  ["apps/api/app/core/brand.py", "WRITTEN: how the API texts spell the name before the swap"],
  ["supabase/templates/build.py", "WRITTEN: how the email texts spell the name before the swap"],
  ["packages/i18n/scripts/export-api.mjs", "swaps the written name in the exported API messages"],
  ["apps/api/app/core/identity.py", "HMAC label of stored hashes: changing it would invalidate every one"],
  ["packages/brand/app-ids.json", "the store id can never change after the first upload"],
  ["packages/brand/scripts/build-assets.mjs", "names the brand file in a message"],
  [".github/workflows/auth-settings-staging.yml", "redirect list of the staging Supabase (docs/brand-rename.md)"],
  [".github/workflows/deploy-apps-web.yml", "Vercel project names (docs/brand-rename.md)"],
  ["infra/legacy-redirects/vercel.json", "points the old address at the current app (docs/brand-rename.md)"],
  ["infra/legacy-redirects/index.html", "points the old address at the current app (docs/brand-rename.md)"],
  ["scripts/backup/backup-db.sh", "backup file names; the restore drill reads them by this prefix"],
  ["scripts/spec-to-docx.cjs", "builds the spec document, not the product"],
  ["scripts/setup-windows.ps1", "the GitHub repository's address"],
  ["apps/client-app/app.json", "generated from the brand file (pnpm brand:sync)"],
  ["supabase/config.toml", "generated from the brand file (pnpm brand:sync)"],
  ["supabase/templates/", "generated from the brand file (pnpm brand:sync)"],
  ["apps/api/app/providers/secrets.py", "development-only key: changing it would orphan local encrypted data"],
  ["apps/api/app/api/schemas.py", "OpenAPI descriptions for developers, and the legacy palette value"],
  ["apps/api/app/api/billing.py", "OpenAPI descriptions for developers"],
  ["apps/api/app/api/migration_notice.py", "OpenAPI descriptions for developers"],
  ["apps/api/app/api/platform.py", "OpenAPI descriptions for developers"],
  ["apps/api/app/api/support.py", "OpenAPI descriptions for developers"],
  [".github/workflows/rehearsal.yml", "names of temporary files"],
  [".github/workflows/e2e.yml", "step titles"],
  [".github/workflows/jobs-staging.yml", "step titles"],
  [".github/workflows/seed-staging.yml", "step descriptions"],
]);

const CODE = /\.(ts|tsx|mjs|cjs|js|py|toml|yml|yaml|sh|ps1|css|html|json)$/;
const SKIPPED = /(^|\/)(tests?|e2e|docs|migrations|node_modules|\.next)\/|\.test\.|\/messages\/|openapi\.json|schema\.ts$|pnpm-lock|uv\.lock/;
const NAME = /(?<![A-Za-z0-9])(MyBiz|mybiz)(app)?(?![A-Za-z])/;

const isAllowed = (path) => [...ALLOWED.keys()].some((entry) => (entry.endsWith("/") ? path.startsWith(entry) : path === entry));

function codeLines(path) {
  const python = path.endsWith(".py");
  let docstring = false;
  const found = [];
  readFileSync(root + path, "utf8")
    .split("\n")
    .forEach((line, index) => {
      const quotes = python ? (line.match(/"""/g) ?? []).length : 0;
      const inside = docstring;
      if (quotes % 2 === 1) docstring = !docstring;
      const text = line.trim();
      if (inside || quotes > 0 || /^(\/\/|\*|\/\*|#|\{\/\*)/.test(text)) return;
      const code = python ? line.replace(/\s#\s.*$/, "") : line.replace(/\s\/\/\s.*$/, "").replace(/\/\*.*?\*\//g, "");
      if (NAME.test(code)) found.push(`${path}:${index + 1}: ${text.slice(0, 100)}`);
    });
  return found;
}

test("the product's name is spelled out only in the brand file and the listed exceptions", () => {
  const files = execFileSync("git", ["ls-files"], { cwd: root, encoding: "utf8" }).split("\n").filter(Boolean);
  const problems = files
    .filter((path) => CODE.test(path) && !SKIPPED.test(path) && !isAllowed(path))
    .flatMap(codeLines);
  assert.deepEqual(problems, [], "Read the name from brand.json instead, or list the file in ALLOWED with the reason");
});

test("every exception still exists and still spells the name", () => {
  for (const path of [...ALLOWED.keys()].filter((entry) => !entry.endsWith("/"))) {
    assert.ok(NAME.test(readFileSync(root + path, "utf8")) || path.endsWith("brand.json"), `${path} no longer needs its exception`);
  }
});
