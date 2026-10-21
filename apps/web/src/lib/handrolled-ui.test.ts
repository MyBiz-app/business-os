import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { elementsIn } from "../../scripts/handrolled-ui-baseline.mjs";

const baseline: Record<string, string[]> = JSON.parse(readFileSync(new URL("../../eslint-rules/handrolled-ui-baseline.json", import.meta.url), "utf8"));

describe("hand-rolled UI baseline (design-system/no-handrolled-ui)", () => {
  it("lists only files that still exist and still need their entry", () => {
    const stale: string[] = [];
    for (const [file, listed] of Object.entries(baseline)) {
      const root = new URL("../../", import.meta.url).pathname;
      if (!existsSync(`${root}${file}`)) {
        stale.push(`${file} (deleted)`);
        continue;
      }
      const used: string[] = elementsIn(file);
      for (const element of listed) if (!used.includes(element)) stale.push(`${file} (no <${element}> left)`);
    }
    assert.deepEqual(stale, [], "A file was migrated: run `node scripts/handrolled-ui-baseline.mjs` in apps/web to shrink the list.");
  });

  it("never lists the components themselves", () => {
    assert.deepEqual(
      Object.keys(baseline).filter((file) => file.startsWith("src/components/ui/")),
      [],
    );
  });
});
