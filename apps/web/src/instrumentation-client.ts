import * as Sentry from "@sentry/nextjs";

import { sentryDsn, sentryOptions } from "@/lib/monitoring";

// Browser error monitoring; does nothing without a DSN.
const dsn = sentryDsn();
if (dsn) Sentry.init(sentryOptions(dsn));

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
