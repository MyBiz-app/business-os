import assert from "node:assert/strict";
import { test } from "node:test";

import { canCredit, readIssueBody, startableKinds } from "./issued-documents.ts";

function form(entries: Record<string, string>): FormData {
  const data = new FormData();
  for (const [key, value] of Object.entries(entries)) data.set(key, value);
  return data;
}

test("exempt dealers and unready businesses cannot start a tax document", () => {
  assert.deepEqual(startableKinds("exempt_dealer", true), ["quote", "transaction_invoice"]);
  assert.deepEqual(startableKinds("licensed_dealer", false), ["quote", "transaction_invoice"]);
  assert.deepEqual(startableKinds("licensed_dealer", true), ["tax_invoice_receipt", "tax_invoice", "quote", "transaction_invoice"]);
});

test("only invoices can be credited", () => {
  assert.equal(canCredit("tax_invoice"), true);
  assert.equal(canCredit("tax_invoice_receipt"), true);
  assert.equal(canCredit("quote"), false);
  assert.equal(canCredit("credit_note"), false);
});

test("lines are read in order, in minor units, skipping empty ones", () => {
  const body = readIssueBody(
    form({
      kind: "quote",
      client_name: "Dana",
      "line.1.description": "Second",
      "line.1.quantity": "2",
      "line.1.price": "10,50",
      "line.0.description": "First",
      "line.0.quantity": "1",
      "line.0.price": "100",
      "line.2.description": "",
      "line.2.price": "5",
    }),
    "ILS",
  );
  assert.deepEqual(body?.lines, [
    { description: "First", quantity: 1, unit_price: 10000 },
    { description: "Second", quantity: 2, unit_price: 1050 },
  ]);
});

test("a document needs a client, lines and a known price", () => {
  const line = { "line.0.description": "x", "line.0.quantity": "1", "line.0.price": "5" };
  assert.equal(readIssueBody(form({ kind: "quote", ...line }), "ILS"), null);
  assert.equal(readIssueBody(form({ kind: "quote", client_name: "A", ...line, "line.0.price": "abc" }), "ILS"), null);
  assert.equal(readIssueBody(form({ kind: "quote", client_name: "A" }), "ILS"), null);
  assert.ok(readIssueBody(form({ kind: "quote", client_id: "c1", ...line }), "ILS"));
});

test("an invoice-receipt needs a payment method and a credit note needs its invoice", () => {
  const base = { client_name: "A", "line.0.description": "x", "line.0.quantity": "1", "line.0.price": "5" };
  assert.equal(readIssueBody(form({ kind: "tax_invoice_receipt", ...base }), "ILS"), null);
  assert.ok(readIssueBody(form({ kind: "tax_invoice_receipt", payment_method: "cash", ...base }), "ILS"));
  assert.equal(readIssueBody(form({ kind: "credit_note", ...base }), "ILS"), null);
  assert.ok(readIssueBody(form({ kind: "credit_note", reference_id: "r1", ...base }), "ILS"));
});
