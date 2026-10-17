/** Deployment-dependent response headers. Read at request time (not build time) so the variables
 * can be changed on the host without a rebuild. Keep this file free of "@/" imports: the node test
 * runner loads it directly. */

type Env = Record<string, string | undefined>;

const TWO_YEARS = 63072000;

/** Search engines may index only where `WEB_ALLOW_INDEXING=true`. Anything else (staging, previews,
 * local) is hidden, so a forgotten variable can never expose demo data to Google. */
export function indexingAllowed(env: Env = process.env): boolean {
  return env.WEB_ALLOW_INDEXING === "true";
}

/** Strict-Transport-Security. `includeSubDomains` is off until the real domain is in place: it makes
 * every subdomain HTTPS-only for two years, and that cannot be undone from the server.
 * Set `WEB_HSTS_INCLUDE_SUBDOMAINS=true` once all subdomains are ready (docs/deploy/go-live-checklist.md). */
export function hstsHeader(env: Env = process.env): string | undefined {
  if (env.NODE_ENV !== "production") return undefined;
  return `max-age=${TWO_YEARS}${env.WEB_HSTS_INCLUDE_SUBDOMAINS === "true" ? "; includeSubDomains" : ""}`;
}

/** `WEB_CSP_MODE=report-only` turns the policy back into report-only without a code change
 * (the emergency switch if a page is found broken in production). */
export function cspReportOnly(env: Env = process.env): boolean {
  return env.WEB_CSP_MODE === "report-only";
}
