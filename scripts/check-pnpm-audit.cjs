// Fails on any high or critical advisory in production dependencies that is not
// allow-listed (with a written reason) in .github/security/pnpm-audit-allowlist.json.
const { spawnSync } = require("node:child_process");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");

const root = join(__dirname, "..");
const allowed = new Map(
  JSON.parse(readFileSync(join(root, ".github/security/pnpm-audit-allowlist.json"), "utf8")).map(
    (entry) => {
      if (!entry.reason) throw new Error(`Allow-list entry ${entry.id} needs a reason`);
      return [entry.id, entry];
    },
  ),
);

// pnpm audit exits non-zero when it finds anything, so read the JSON and ignore the code.
const run = spawnSync("pnpm", ["audit", "--prod", "--audit-level", "high", "--json"], {
  cwd: root,
  encoding: "utf8",
  maxBuffer: 64 * 1024 * 1024,
});
let report;
try {
  report = JSON.parse(run.stdout);
} catch {
  console.error("pnpm audit did not return JSON:\n" + run.stdout + run.stderr);
  process.exit(1);
}

const found = Object.values(report.advisories ?? {}).filter((a) =>
  ["high", "critical"].includes(a.severity),
);
const blocking = found.filter((a) => !allowed.has(a.github_advisory_id));
for (const a of found) {
  const tag = allowed.has(a.github_advisory_id) ? "allowed" : "BLOCKING";
  console.log(`[${tag}] ${a.severity} ${a.module_name} ${a.github_advisory_id}: ${a.title}`);
}
if (blocking.length > 0) {
  console.error(
    `${blocking.length} high/critical advisories. Upgrade the package, or allow-list the advisory with a reason in .github/security/pnpm-audit-allowlist.json.`,
  );
  process.exit(1);
}
console.log("pnpm audit: no un-allow-listed high or critical advisories.");
