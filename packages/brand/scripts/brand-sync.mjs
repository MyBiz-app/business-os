// Copies what the Python side and the config files need from packages/i18n/brand.json, the one
// brand file. `pnpm brand:sync` rewrites them; `pnpm brand:sync --check` fails when one is stale
// (CI runs it). The supabase/templates/*.html files come from build.py, which reads the same file.
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = (path) => fileURLToPath(new URL(`../../../${path}`, import.meta.url));
const brandText = readFileSync(root("packages/i18n/brand.json"), "utf8");
const brand = JSON.parse(brandText);
const check = process.argv.includes("--check");

const schemes = [brand.app.scheme, ...brand.app.legacySchemes];

/** Each target: its path and a function from the current text to the wanted text. */
const targets = {
  // The API image is built from apps/api alone, so it carries a copy of the brand file.
  "apps/api/app/core/brand.json": () => brandText,
  "supabase/config.toml": (text) =>
    text
      .replace(/(additional_redirect_urls = \[[^\]]*?)(, "[a-z][a-z0-9+.-]*:\/\/\*\*")+\]/, (_, head) =>
        `${head}${schemes.map((s) => `, "${s}://**"`).join("")}]`)
      .replace(/(subject = "You've been invited · הוזמנתם ל-)[^"]*"/, `$1${brand.name}"`),
  "apps/client-app/app.json": (text) => {
    const json = JSON.parse(text);
    json.expo.name = brand.name;
    json.expo.scheme = schemes.length === 1 ? schemes[0] : schemes;
    const swap = (value) => (typeof value === "string" ? value.replace(/^Allow .+? to /, `Allow ${brand.name} to `) : value);
    for (const plugin of json.expo.plugins ?? []) {
      if (Array.isArray(plugin) && plugin[1] && typeof plugin[1] === "object") {
        for (const key of Object.keys(plugin[1])) plugin[1][key] = swap(plugin[1][key]);
      }
    }
    for (const key of Object.keys(json.expo.ios?.infoPlist ?? {})) {
      json.expo.ios.infoPlist[key] = swap(json.expo.ios.infoPlist[key]);
    }
    return `${JSON.stringify(json, null, 2)}\n`;
  },
};

const stale = [];
for (const [path, wanted] of Object.entries(targets)) {
  const current = existsSync(root(path)) ? readFileSync(root(path), "utf8") : "";
  const next = wanted(current);
  if (next === current) continue;
  stale.push(path);
  if (!check) writeFileSync(root(path), next);
}

// The translations the API renders carry the name too; the i18n test checks them in CI.
if (!check) execFileSync("node", [root("packages/i18n/scripts/export-api.mjs")], { stdio: "pipe" });

try {
  execFileSync("python3", [root("supabase/templates/build.py"), ...(check ? ["--check"] : [])], { stdio: "pipe" });
} catch (error) {
  if (check) stale.push("supabase/templates/*.html");
  else throw error;
}

if (check && stale.length) {
  console.error(`Out of sync with packages/i18n/brand.json: ${stale.join(", ")}. Run: pnpm brand:sync`);
  process.exit(1);
}
console.log(check ? "Brand copies are in sync." : `Synced ${stale.length ? stale.join(", ") : "nothing (already up to date)"}.`);
