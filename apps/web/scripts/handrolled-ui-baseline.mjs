// Writes eslint-rules/handrolled-ui-baseline.json: the files that still use a bare <button> or
// <table> and so are exempt from design-system/no-handrolled-ui. The list is a ratchet: it only
// shrinks. Run it after migrating a file to Button / DataTable (`node scripts/handrolled-ui-baseline.mjs`);
// src/lib/handrolled-ui.test.ts fails while a listed file no longer needs its entry.
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, relative, sep } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const ELEMENTS = { button: /<button(?=[\s>/])/, table: /<table(?=[\s>/])/ };

/** Source files the rule applies to: everything in src except the components themselves and stories. */
export function checkedFiles() {
  const out = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path);
      else if (/\.tsx$/.test(entry.name) && !/\.stories\.tsx$/.test(entry.name)) out.push(relative(root, path).split(sep).join("/"));
    }
  };
  walk(join(root, "src"));
  return out.filter((file) => !file.startsWith("src/components/ui/"));
}

/** Which of the two elements a file uses, by text. */
export function elementsIn(file) {
  const text = readFileSync(join(root, file), "utf8");
  return Object.entries(ELEMENTS)
    .filter(([, pattern]) => pattern.test(text))
    .map(([name]) => name);
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  const baseline = {};
  for (const file of checkedFiles().sort()) {
    const used = elementsIn(file);
    if (used.length) baseline[file] = used;
  }
  writeFileSync(join(root, "eslint-rules/handrolled-ui-baseline.json"), `${JSON.stringify(baseline, null, 2)}\n`);
  console.log(`${Object.keys(baseline).length} files in the baseline`);
}
