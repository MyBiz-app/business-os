import assert from "node:assert/strict";
import { test } from "node:test";

import { callHref, internationalDigits, whatsappHref } from "./contact.ts";

test("a local Israeli number becomes international for WhatsApp", () => {
  assert.equal(whatsappHref("050-123 4567", "ILS"), "https://wa.me/972501234567");
  assert.equal(internationalDigits("0501234567", "ILS"), "972501234567");
});

test("a number with a plus or 00 is taken as typed, whatever the currency", () => {
  assert.equal(whatsappHref("+972501234567", "USD"), "https://wa.me/972501234567");
  assert.equal(whatsappHref("0044 20 7946 0958", "ILS"), "https://wa.me/442079460958");
});

test("a US number gets the US country code; an unknown country gets no WhatsApp link", () => {
  assert.equal(whatsappHref("(415) 555-0100", "USD"), "https://wa.me/14155550100");
  assert.equal(whatsappHref("0201234567", "EUR"), null);
});

test("the call link keeps the number as saved, without spaces", () => {
  assert.equal(callHref("+972 50 123 4567"), "tel:+972501234567");
  assert.equal(callHref("050-1234567"), "tel:0501234567");
});
