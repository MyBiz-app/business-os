import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

const SRC = join(import.meta.dirname, "..");
const read = (path: string) => readFileSync(join(SRC, path), "utf8");

describe("wide-screen policy", () => {
  it("gives the settings room and the staff card the 1600px container", () => {
    assert.match(read("app/(app)/(tenant)/settings/layout.tsx"), /size="settings"/);
    assert.match(read("app/(app)/(tenant)/team/[userId]/page.tsx"), /size="settings"/);
    assert.ok(read("components/layout/container.tsx").includes('settings: "max-w-[100rem]"'));
  });

  it("flows every settings topic into columns inside a container query", () => {
    const dir = join(SRC, "app/(app)/(tenant)/settings");
    const topics = readdirSync(dir, { withFileTypes: true }).filter((e) => e.isDirectory());
    for (const topic of topics) {
      const page = join(dir, topic.name, "page.tsx");
      let source = "";
      try {
        source = readFileSync(page, "utf8");
      } catch {
        continue;
      }
      if (source.includes("CollapsibleSection")) assert.ok(source.includes("form-columns"), topic.name);
    }
    expect(read("app/(app)/(tenant)/settings/settings-room.tsx")).toContain("@container");
    assert.match(read("app/globals.css"), /@container \(min-width: 56rem\)/);
  });

  it("adds columns to the cards from 1920px and keeps six dashboard tiles in a row", () => {
    expect(read("app/(app)/(tenant)/clients/[id]/page.tsx")).toContain("min-[120rem]:grid-cols-7");
    expect(read("app/(app)/(tenant)/team/[userId]/card-sections.tsx")).toContain("min-[120rem]:grid-cols-3");
    expect(read("app/(app)/(tenant)/dashboard/page.tsx")).toContain("2xl:grid-cols-6");
  });
});
