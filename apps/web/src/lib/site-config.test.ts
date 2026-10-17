import assert from "node:assert/strict";
import { test } from "node:test";

import { cspReportOnly, hstsHeader, indexingAllowed } from "./site-config.ts";

test("search engines are blocked unless indexing is switched on explicitly", () => {
  assert.equal(indexingAllowed({}), false);
  assert.equal(indexingAllowed({ WEB_ALLOW_INDEXING: "yes" }), false);
  assert.equal(indexingAllowed({ WEB_ALLOW_INDEXING: "true" }), true);
});

test("HSTS is production only and includeSubDomains waits for the switch", () => {
  assert.equal(hstsHeader({ NODE_ENV: "development" }), undefined);
  assert.equal(hstsHeader({ NODE_ENV: "production" }), "max-age=63072000");
  assert.equal(hstsHeader({ NODE_ENV: "production", WEB_HSTS_INCLUDE_SUBDOMAINS: "true" }), "max-age=63072000; includeSubDomains");
});

test("the CSP is enforced unless report-only is requested", () => {
  assert.equal(cspReportOnly({}), false);
  assert.equal(cspReportOnly({ WEB_CSP_MODE: "report-only" }), true);
});
