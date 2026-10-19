// Fails when a relative link in a tracked Markdown file points at a file or folder that does not exist.
// External links (http, mailto) and in-page anchors are not checked. Run: node scripts/check-doc-links.cjs
const { execFileSync } = require("node:child_process");
const { readFileSync, existsSync } = require("node:fs");
const path = require("node:path");

const files = execFileSync("git", ["ls-files", "-z", "--cached", "--others", "--exclude-standard", "*.md"], {
  encoding: "utf8",
  maxBuffer: 1 << 28,
})
  .split("\0")
  .filter((f) => f && !f.includes("node_modules/") && existsSync(f));

const LINK = /\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g;
const broken = [];
for (const file of files) {
  const lines = readFileSync(file, "utf8").split("\n");
  let inFence = false;
  lines.forEach((line, i) => {
    if (/^\s*```/.test(line)) inFence = !inFence;
    if (inFence) return;
    for (const m of line.matchAll(LINK)) {
      let target = m[1];
      if (/^([a-z][a-z0-9+.-]*:|#|\/)/i.test(target)) continue;
      target = decodeURIComponent(target.split("#")[0].split("?")[0]);
      if (!target) continue;
      if (!existsSync(path.join(path.dirname(file), target))) broken.push(`${file}:${i + 1}: ${m[1]}`);
    }
  });
}

if (broken.length) {
  console.error("Broken relative links in Markdown files:\n" + broken.join("\n"));
  process.exit(1);
}
console.log(`All relative links resolve (${files.length} Markdown files checked).`);
