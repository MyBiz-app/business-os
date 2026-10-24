// Vercel's upload skips any folder named node_modules, and `expo export` puts the fonts and icons of
// packages under dist/assets/__node_modules/<package path>/node_modules/... The files never arrived, the
// host answered with index.html, and the app showed default fonts and no icons. This moves those files to
// dist/assets/files/ (their names already carry a content hash) and rewrites the references in the bundle.
// Usage: node scripts/relocate-assets.mjs [dist]
import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { basename, join } from "node:path";

const dist = process.argv[2] ?? "dist";
const from = join(dist, "assets", "__node_modules");
if (!existsSync(from)) {
  console.log("No __node_modules assets, nothing to move.");
  process.exit(0);
}

const to = join(dist, "assets", "files");
mkdirSync(to, { recursive: true });
const walk = (dir) => readdirSync(dir).flatMap((name) => {
  const path = join(dir, name);
  return statSync(path).isDirectory() ? walk(path) : [path];
});
const moved = new Set();
for (const file of walk(from)) {
  const name = basename(file);
  if (moved.has(name)) throw new Error(`Two assets share the name ${name}`);
  moved.add(name);
  renameSync(file, join(to, name));
}
rmSync(from, { recursive: true, force: true });

let rewritten = 0;
for (const file of walk(dist).filter((f) => /\.(js|html|json|css)$/.test(f))) {
  const text = readFileSync(file, "utf8");
  const next = text.replace(/\/assets\/__node_modules\/[^"'`)\s]*\/([^/"'`)\s]+)/g, "/assets/files/$1");
  if (next !== text) {
    writeFileSync(file, next);
    rewritten += 1;
  }
}
console.log(`Moved ${moved.size} files to assets/files, rewrote ${rewritten} bundle files.`);
if (walk(dist).some((f) => /\.(js|html|json|css)$/.test(f) && readFileSync(f, "utf8").includes("__node_modules")))
  throw new Error("A reference to __node_modules is left in the build.");
