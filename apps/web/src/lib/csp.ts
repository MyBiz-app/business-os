/** Content-Security-Policy for the web app: a strict, nonce-based policy set per request by the proxy
 * (src/proxy.ts). Scripts run only with this request's nonce ('strict-dynamic' lets Next.js load its
 * own chunks); violations are reported to /api/csp-report.
 *
 * The browser never calls the API or Supabase directly (every call goes through the Next.js
 * server), so connect-src stays 'self' plus the free map tile host (the branches map, R35), which
 * is the one thing the browser fetches itself.
 * Keep this file free of "@/" imports: the node test runner loads it directly. */

export const CSP_REPORT_PATH = "/api/csp-report";

/** The request header the proxy uses to hand the nonce to server components. */
export const NONCE_HEADER = "x-nonce";

/** 128 random bits, base64: a fresh one for every page request. */
export function createNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}

/** `embeddable`: a page other sites may show in a frame (the contact form a business pastes into
 * its own website). */
type Options = { dev: boolean; embeddable?: boolean };

/** The host error reports go to (Sentry), from the DSN; nothing when monitoring is off. */
export function sentryIngestOrigin(dsn: string | undefined = process.env.NEXT_PUBLIC_SENTRY_DSN): string | undefined {
  if (!dsn) return undefined;
  try {
    return new URL(dsn).origin;
  } catch {
    return undefined;
  }
}

/** The free OpenStreetMap-based tile service behind the branches map (styles, tiles, fonts). */
export const MAP_ORIGIN = "https://tiles.openfreemap.org";

/** The API's origin: business logos and other public images are served from it. */
export function apiOrigin(url: string | undefined = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"): string | undefined {
  try {
    return new URL(url).origin;
  } catch {
    return undefined;
  }
}

function directives(scriptSrc: string, { dev, embeddable }: Options): string[] {
  return [
    "default-src 'self'",
    `script-src ${scriptSrc}${dev ? " 'unsafe-eval'" : ""}`,
    // React and next/font set inline style attributes; a style nonce cannot cover those.
    "style-src 'self' 'unsafe-inline'",
    ["img-src 'self' data: blob:", MAP_ORIGIN, apiOrigin()].filter(Boolean).join(" "),
    "font-src 'self' data:",
    ["connect-src 'self'", MAP_ORIGIN, sentryIngestOrigin()].filter(Boolean).join(" "),
    // The map draws on a canvas in a worker made from a blob.
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    // The app is never shown inside another site's frame (clickjacking), except the one public
    // page built for it.
    embeddable ? "frame-ancestors *" : "frame-ancestors 'none'",
  ];
}

/** The policy: only scripts carrying this request's nonce, plus what they load
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
