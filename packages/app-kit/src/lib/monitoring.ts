import * as Sentry from "@sentry/react-native";

// Error monitoring for the Expo apps: off unless EXPO_PUBLIC_SENTRY_DSN is set. No personal data
// leaves the device: request details and user details are stripped from every event.
const DSN = process.env.EXPO_PUBLIC_SENTRY_DSN || undefined;

type EventLike = { request?: { method?: string; url?: string }; user?: unknown };

export function scrubEvent<T extends EventLike>(event: T): T {
  if (event.request) {
    event.request = { method: event.request.method, url: event.request.url?.split("?")[0] };
  }
  delete event.user;
  return event;
}

let started = false;

/** Start error reporting once; does nothing without a DSN. Call it at app start. */
export function initMonitoring(): boolean {
  if (!DSN) return false;
  if (!started) {
    started = true;
    Sentry.init({
      dsn: DSN,
      environment: process.env.EXPO_PUBLIC_SENTRY_ENVIRONMENT || (__DEV__ ? "development" : "production"),
      sendDefaultPii: false,
      tracesSampleRate: Number(process.env.EXPO_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? 0),
      beforeSend: scrubEvent,
    });
  }
  return true;
}

/** Report an error the app caught itself (does nothing without a DSN). */
export function reportError(error: unknown): void {
  if (DSN) Sentry.captureException(error);
}
