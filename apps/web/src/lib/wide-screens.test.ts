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

  it("keeps every collapsible settings topic in one column and only small card grids in two", () => {
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
      if (source.includes("CollapsibleSection") && topic.name !== "integrations") {
        assert.ok(source.includes("form-columns"), topic.name);
        assert.ok(!source.includes("form-grid"), topic.name);
      }
    }
    assert.ok(read("app/(app)/(tenant)/settings/integrations/page.tsx").includes("form-grid"));
    assert.ok(read("app/(app)/(tenant)/settings/settings-room.tsx").includes("@container"));
    assert.match(read("app/globals.css"), /@container \(min-width: 56rem\)/);
  });

  it("gives the client and lead cards the settings width with an inner menu and one column", () => {
    for (const card of ["clients", "leads"]) {
      assert.match(read(`app/(app)/(tenant)/${card}/[id]/page.tsx`), /size="settings"/);
      assert.ok(read(`app/(app)/(tenant)/${card}/[id]/${card === "clients" ? "client" : "lead"}-body.tsx`).includes("RecordLayout"), card);
    }
    assert.ok(!read("app/(app)/(tenant)/clients/[id]/client-body.tsx").includes("min-[120rem]:grid-cols"));
  });

  it("adds columns to the staff card from 1920px and keeps the four dashboard numbers in one row", () => {
    assert.ok(read("app/(app)/(tenant)/team/[userId]/card-sections.tsx").includes("min-[120rem]:grid-cols-3"));
    assert.ok(read("app/(app)/(tenant)/dashboard/page.tsx").includes("lg:grid-cols-4"));
  });
});
