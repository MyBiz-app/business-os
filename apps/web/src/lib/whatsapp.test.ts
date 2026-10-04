import assert from "node:assert/strict";
import { test } from "node:test";

import { internationalDigits, whatsappLink } from "./whatsapp.ts";

test("local Israeli numbers become international", () => {
  assert.equal(internationalDigits("050-123 4567", "Asia/Jerusalem"), "972501234567");
});

test("international numbers are kept", () => {
  assert.equal(internationalDigits("+1 (212) 555-0100", "Asia/Jerusalem"), "12125550100");
});

test("the text is encoded", () => {
  assert.equal(
    whatsappLink("0501234567", "Asia/Jerusalem", "שלום דנה"),
    "https://wa.me/972501234567?text=%D7%A9%D7%9C%D7%95%D7%9D%20%D7%93%D7%A0%D7%94",
  );
});

test("junk is rejected", () => {
  assert.equal(whatsappLink("12", "Asia/Jerusalem"), null);
});
