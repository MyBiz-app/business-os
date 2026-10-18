import assert from "node:assert/strict";
import { test } from "node:test";

import { apiOrigin, createNonce, parseCspReports, strictCsp } from "./csp.ts";

test("nonces are fresh 128-bit base64 values", () => {
  const a = createNonce();
  assert.match(a, /^[A-Za-z0-9+/]{22}==$/);
  assert.notEqual(a, createNonce());
});

test("the policy allows scripts only by nonce and reports violations", () => {
  const policy = strictCsp("abc", { dev: false });
  assert.match(policy, /script-src 'self' 'nonce-abc' 'strict-dynamic'(;|$)/);
  assert.doesNotMatch(policy, /script-src[^;]*'unsafe-(inline|eval)'/);
  assert.match(policy, /connect-src 'self'(;|$)/);
  assert.match(policy, /frame-ancestors 'none'/);
  assert.match(policy, /object-src 'none'/);
  assert.match(policy, /report-uri \/api\/csp-report/);
});

test("only the embeddable contact form may be shown in another site's frame", () => {
  assert.match(strictCsp("abc", { dev: false, embeddable: true }), /frame-ancestors \*(;|$)/);
  assert.doesNotMatch(strictCsp("abc", { dev: false }), /frame-ancestors \*/);
});

test("images may load from the API origin (business logos)", () => {
  assert.equal(apiOrigin("https://api.example.com/v1"), "https://api.example.com");
  assert.equal(apiOrigin("not a url"), undefined);
  assert.match(strictCsp("abc", { dev: false }), /img-src 'self' data: blob: http[^;]*(;|$)/);
});

test("dev mode allows eval (React refresh)", () => {
  const policy = strictCsp("abc", { dev: true });
  assert.match(policy, /script-src [^;]*'unsafe-eval'/);
});

test("parses legacy report-uri reports and drops query strings", () => {
  const reports = parseCspReports({
    "csp-report": {
      "document-uri": "https://app.example/join/abc?code=secret",
      "violated-directive": "script-src-elem",
      "blocked-uri": "inline",
      "source-file": "https://app.example/page?x=1",
      "line-number": 3,
    },
  });
  assert.deepEqual(reports, [
    { directive: "script-src-elem", blocked: "inline", page: "https://app.example/join/abc", source: "https://app.example/page:3" },
  ]);
});

test("parses Reporting API reports and ignores other report types", () => {
  const reports = parseCspReports([
    { type: "deprecation", body: {} },
    {
      type: "csp-violation",
      body: { documentURL: "https://app.example/", effectiveDirective: "connect-src", blockedURL: "https://evil.example/x?y", disposition: "report" },
    },
  ]);
  assert.deepEqual(reports, [
    { directive: "connect-src", blocked: "https://evil.example/x", page: "https://app.example/", disposition: "report" },
  ]);
});

test("garbage payloads yield nothing", () => {
  assert.deepEqual(parseCspReports(null), []);
  assert.deepEqual(parseCspReports("x"), []);
  assert.deepEqual(parseCspReports({ "csp-report": 5 }), []);
});
