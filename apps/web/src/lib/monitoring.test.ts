import assert from "node:assert/strict";
import test from "node:test";

import { scrubEvent, sentryIngestOrigin } from "./monitoring.ts";

test("scrubEvent keeps the method and the URL without its query, and drops the user", () => {
  const event = scrubEvent({
    request: { method: "GET", url: "https://x.test/clients?email=a@b.com", cookies: { s: "1" }, data: "x" },
    user: { email: "a@b.com" },
  });
  assert.deepEqual(event.request, { method: "GET", url: "https://x.test/clients" });
  assert.equal("user" in event, false);
});

test("sentryIngestOrigin is the host without credentials, and nothing without a DSN", () => {
  assert.equal(sentryIngestOrigin("https://abc123@o1.ingest.sentry.io/42"), "https://o1.ingest.sentry.io");
  assert.equal(sentryIngestOrigin(undefined), undefined);
  assert.equal(sentryIngestOrigin("not a url"), undefined);
});
