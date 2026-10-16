// Fails when an em dash or en dash appears in tracked text files (product rule: plain "-" only).
// Built from char codes so this file stays free of the characters it forbids. Run: node scripts/check-no-long-dash.cjs
const { execFileSync } = require("node:child_process");
const { readFileSync } = require("node:fs");

const FORBIDDEN = new RegExp("[" + String.fromCharCode(0x2014, 0x2013) + "]");
// Generated, vendored or binary-ish files and the original owner spec are exempt.
const SKIP = [/^pnpm-lock\.yaml$/, /^docs\/spec\//, /^packages\/api-client\/(openapi\.json|src\/schema\.ts)$/];

const files = execFileSync("git", ["ls-files", "-z"], { encoding: "utf8", maxBuffer: 1 << 28 })
  .split("\0")
  .filter((f) => f && !SKIP.some((re) => re.test(f)));

const hits = [];
for (const file of files) {
  let text;
  try {
    const buf = readFileSync(file);
    if (buf.includes(0)) continue; // binary
    text = buf.toString("utf8");
  } catch {
    continue;
  }
  text.split("\n").forEach((line, i) => {
    if (FORBIDDEN.test(line)) hits.push(`${file}:${i + 1}: ${line.trim().slice(0, 100)}`);
  });
}

if (hits.length) {
  console.error('Long dashes (em or en) are not allowed; use a plain hyphen "-":\n' + hits.join("\n"));
  process.exit(1);
}
console.log("No long dashes found.");
