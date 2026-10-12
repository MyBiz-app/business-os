/** Content-Security-Policy for the web app. Two policies run side by side:
 *
 * - the enforced one (next.config.ts) still allows inline scripts, so nothing can break;
 * - a strict, nonce-based one, sent per request by the proxy as Report-Only. Browsers report what
 *   it would block to /api/csp-report. Once the reports are clean it replaces the enforced one.
 *
 * The browser never calls the API or Supabase directly (every call goes through the Next.js
 * server), so connect-src stays 'self', which is tighter than listing those origins.
 * Keep this file free of "@/" imports: next.config.ts and the node test runner load it directly. */

export const CSP_REPORT_PATH = "/api/csp-report";

/** The request header the proxy uses to hand the nonce to server components. */
export const NONCE_HEADER = "x-nonce";

/** 128 random bits, base64: a fresh one for every page request. */
export function createNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}

type Options = { dev: boolean };

/** The host error reports go to (Sentry), from the DSN; nothing when monitoring is off. */
export function sentryIngestOrigin(dsn: string | undefined = process.env.NEXT_PUBLIC_SENTRY_DSN): string | undefined {
  if (!dsn) return undefined;
  try {
    return new URL(dsn).origin;
  } catch {
    return undefined;
  }
}

function directives(scriptSrc: string, { dev }: Options): string[] {
  return [
    "default-src 'self'",
    `script-src ${scriptSrc}${dev ? " 'unsafe-eval'" : ""}`,
    // React and next/font set inline style attributes; a style nonce cannot cover those.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    ["connect-src 'self'", sentryIngestOrigin()].filter(Boolean).join(" "),
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    // The app is never shown inside another site's frame (clickjacking).
    "frame-ancestors 'none'",
  ];
}

/** The enforced policy: inline scripts are still allowed (see the file comment). */
export function enforcedCsp(options: Options): string {
  return directives("'self' 'unsafe-inline'", options).join("; ");
}

/** The strict policy: only scripts carrying this request's nonce, plus what they load
 * ('strict-dynamic' lets Next.js load its own chunks). */
export function strictCsp(nonce: string, options: Options): string {
  return [
    ...directives(`'self' 'nonce-${nonce}' 'strict-dynamic'`, options),
    `report-uri ${CSP_REPORT_PATH}`,
    "report-to csp",
  ].join("; ");
}

/** The Reporting API endpoint named by `report-to csp` (newer browsers use it over report-uri). */
export const REPORTING_ENDPOINTS = `csp="${CSP_REPORT_PATH}"`;

export type CspViolation = {
  directive: string;
  blocked: string;
  page: string;
  source?: string;
  disposition?: string;
};

function trimUrl(value: unknown): string {
  if (typeof value !== "string") return "";
  // Query strings can carry tokens (e.g. a join code); the path is enough to find the cause.
  try {
    const url = new URL(value);
    return `${url.origin}${url.pathname}`;
  } catch {
    return value.slice(0, 200);
  }
}

/** Reads both report formats: the legacy `{"csp-report": {...}}` (report-uri) and the
 * Reporting API list `[{type: "csp-violation", body: {...}}]` (report-to). */
export function parseCspReports(payload: unknown): CspViolation[] {
  const bodies: Record<string, unknown>[] = [];
  if (Array.isArray(payload)) {
    for (const report of payload.slice(0, 20)) {
      if (report && typeof report === "object" && report.type === "csp-violation" && report.body && typeof report.body === "object") {
        bodies.push(report.body as Record<string, unknown>);
      }
    }
  } else if (payload && typeof payload === "object" && "csp-report" in payload) {
    const legacy = (payload as Record<string, unknown>)["csp-report"];
    if (legacy && typeof legacy === "object") bodies.push(legacy as Record<string, unknown>);
  }
  return bodies.map((body) => {
    const pick = (...keys: string[]) => keys.map((key) => body[key]).find((value) => typeof value === "string") as string | undefined;
    const sourceFile = pick("sourceFile", "source-file");
    const line = body.lineNumber ?? body["line-number"];
    return {
      directive: (pick("effectiveDirective", "effective-directive", "violated-directive") ?? "").slice(0, 100),
      blocked: trimUrl(pick("blockedURL", "blocked-uri")),
      page: trimUrl(pick("documentURL", "document-uri")),
      ...(sourceFile ? { source: `${trimUrl(sourceFile)}${typeof line === "number" ? `:${line}` : ""}` } : {}),
      ...(pick("disposition") ? { disposition: pick("disposition") } : {}),
    };
  });
}
