import * as Sentry from "@sentry/nextjs";

import { sentryDsn, sentryOptions } from "@/lib/monitoring";

/** Server and edge error monitoring; does nothing without a DSN. */
export function register() {
  const dsn = sentryDsn();
  if (dsn) Sentry.init(sentryOptions(dsn));
}

export const onRequestError = Sentry.captureRequestError;
