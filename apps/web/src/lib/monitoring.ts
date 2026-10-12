/** Error monitoring (Sentry) settings shared by the server, edge and browser. Monitoring is off
 * unless `NEXT_PUBLIC_SENTRY_DSN` is set. No personal data leaves: request bodies, cookies,
 * headers, query strings and user details are stripped from every event. */

export const sentryDsn = (): string | undefined => process.env.NEXT_PUBLIC_SENTRY_DSN || undefined;

type SentryEventLike = { request?: { method?: string; url?: string }; user?: unknown };

export function scrubEvent<T extends SentryEventLike>(event: T): T {
  if (event.request) {
    event.request = { method: event.request.method, url: event.request.url?.split("?")[0] };
  }
  delete event.user;
  return event;
}

/** The host events are sent to, for the page's Content-Security-Policy `connect-src`. */
export function sentryIngestOrigin(dsn: string | undefined): string | undefined {
  if (!dsn) return undefined;
  try {
    return new URL(dsn).origin.replace(/^(https?:\/\/)[^@]*@/, "$1");
  } catch {
    return undefined;
  }
}

export const sentryOptions = (dsn: string) => ({
  dsn,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? process.env.NODE_ENV,
  sendDefaultPii: false,
  tracesSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? 0),
  beforeSend: scrubEvent,
});
