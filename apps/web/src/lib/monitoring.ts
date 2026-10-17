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

export const sentryOptions = (dsn: string) => ({
  dsn,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? process.env.NODE_ENV,
  release: process.env.NEXT_PUBLIC_SENTRY_RELEASE || undefined,
  sendDefaultPii: false,
  tracesSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? 0),
  beforeSend: scrubEvent,
});
