import { readFileSync } from "node:fs";
import { join } from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

const SRC = join(import.meta.dirname, "..");
const read = (path: string) => readFileSync(join(SRC, path), "utf8");
const TEAM = "app/(app)/(tenant)/team";

describe("staff card (R5)", () => {
  const sections = read(`${TEAM}/[userId]/card-sections.tsx`);

  it("folds every block and remembers it per person", () => {
    assert.match(sections, /<CollapsibleSection[\s\S]*storageKey=\{`staff-card-/);
  });

  it("lists payslips and the contract in the documents tab, filtered to the person", () => {
    assert.match(sections, /payslipsTitle/);
    assert.match(sections, /contractTitle/);
    assert.match(sections, /"payroll"/);
    assert.match(sections, /"employees"/);
    assert.match(sections, /owner_user_id/);
  });

  it("shows the agents open to the person in the AI tab", () => {
    assert.match(sections, /agentsTitle/);
    assert.match(sections, /allowed_roles/);
  });

  it("opens as a window over the team list, and as a page on its own URL", () => {
    assert.match(read(`${TEAM}/page.tsx`), /StaffCardWindow/);
    assert.match(read(`${TEAM}/staff-card-window.tsx`), /RouteModal/);
    assert.match(read(`${TEAM}/team-forms.tsx`), /CardTransition/);
    assert.match(read(`${TEAM}/[userId]/page.tsx`), /StaffCardBody/);
  });

  it("has the same new keys in Hebrew and English", () => {
    for (const key of ["payslipsTitle", "noPayslips", "contractTitle", "noContract", "agentsTitle", "noAgents", "openAgents"]) {
      for (const locale of ["he", "en"]) {
        const json = JSON.parse(readFileSync(join(SRC, `../../../packages/i18n/messages/${locale}.json`), "utf8"));
        assert.ok(json.staffCard?.[key], `${locale}.staffCard.${key}`);
      }
    }
  });
});
