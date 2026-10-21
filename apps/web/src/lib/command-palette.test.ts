import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { fold, hitHref, matches, MAX_RECENTS, parseRecents, quickActionsFor, toPaletteHit, withRecent, type PaletteHit } from "./command-palette.ts";

const labels = {
  stage: { new: "New" },
  role: { front_desk: "Front desk" },
  document: { tax_invoice: "Tax invoice" },
  when: (instant: string) => `at ${instant.slice(11, 16)}`,
};

const hit = (n: number): PaletteHit => ({ kind: "client", id: `id-${n}`, title: `Client ${n}`, meta: "", href: `/clients/id-${n}` });

describe("toPaletteHit", () => {
  it("links each kind to its own page", () => {
    assert.equal(hitHref("client", "a"), "/clients/a");
    assert.equal(hitHref("lead", "a"), "/leads/a");
    assert.equal(hitHref("staff", "a"), "/team/a");
    assert.equal(hitHref("session", "a"), "/schedule/a");
    assert.equal(hitHref("invoice", "a"), "/invoices/a");
  });
  it("describes a lead by stage and interest", () => {
    const shown = toPaletteHit({ kind: "lead", id: "l1", title: "Dana", subtitle: "Pilates", tag: "new" }, labels);
    assert.equal(shown.meta, "New · Pilates");
  });
  it("describes an invoice by kind, number and day", () => {
    const shown = toPaletteHit({ kind: "invoice", id: "i1", title: "Dana", tag: "tax_invoice", number: 1001, at: "2026-10-21T09:30:00Z" }, labels);
    assert.equal(shown.meta, "Tax invoice · #1001 · at 09:30");
  });
  it("leaves out what is missing", () => {
    assert.equal(toPaletteHit({ kind: "client", id: "c1", title: "Dana" }, labels).meta, "");
    assert.equal(toPaletteHit({ kind: "staff", id: "s1", title: "Sam", tag: "unknown" }, labels).meta, "");
  });
});

describe("quickActionsFor", () => {
  it("offers only what the permissions allow", () => {
    assert.deepEqual(quickActionsFor([], []), []);
    assert.deepEqual(
      quickActionsFor(["sales.manage"], []).map((a) => a.id),
      ["newQuote", "newInvoice"],
    );
  });
  it("offers a new lead only with the CRM module", () => {
    assert.ok(!quickActionsFor(["clients.write"], []).some((a) => a.id === "newLead"));
    assert.ok(quickActionsFor(["clients.write"], ["crm"]).some((a) => a.id === "newLead"));
  });
  it("needs both permissions to book an appointment", () => {
    assert.ok(!quickActionsFor(["bookings.manage"], []).some((a) => a.id === "bookAppointment"));
    assert.ok(quickActionsFor(["bookings.manage", "schedule.read"], []).some((a) => a.id === "bookAppointment"));
  });
});

describe("matches", () => {
  it("ignores case, accents and word order", () => {
    assert.equal(fold("Café"), "cafe");
    assert.ok(matches("New client", "CLIENT new"));
    assert.ok(matches("Café Bar", "cafe"));
  });
  it("needs every word", () => {
    assert.ok(!matches("New client", "new lead"));
    assert.ok(!matches("New client", "   "));
  });
  it("works in Hebrew", () => {
    assert.ok(matches("לקוח חדש", "חדש"));
  });
});

describe("recents", () => {
  it("keeps the newest first, without repeats, up to five", () => {
    let list: PaletteHit[] = [];
    for (let n = 1; n <= 7; n++) list = withRecent(list, hit(n));
    assert.equal(list.length, MAX_RECENTS);
    assert.equal(list[0].id, "id-7");
    list = withRecent(list, hit(5));
    assert.deepEqual(list.map((h) => h.id), ["id-5", "id-7", "id-6", "id-4", "id-3"]);
  });
  it("reads back what it stored, and nothing else", () => {
    assert.deepEqual(parseRecents(JSON.stringify([hit(1)])), [hit(1)]);
    assert.deepEqual(parseRecents(null), []);
    assert.deepEqual(parseRecents("not json"), []);
    assert.deepEqual(parseRecents('{"a":1}'), []);
  });
  it("drops entries that are not a local link", () => {
    const evil = { ...hit(1), href: "https://evil.example/x" };
    const protocolRelative = { ...hit(2), href: "//evil.example/x" };
    assert.deepEqual(parseRecents(JSON.stringify([evil, protocolRelative, hit(3)])), [hit(3)]);
  });
});
