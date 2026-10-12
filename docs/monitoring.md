# Monitoring: errors and uptime

Both are off by default and switch on with settings; nothing is sent while no DSN is set. No
personal data is reported: request bodies, cookies, headers, query strings and user details are
stripped before an event leaves the API, the web app or the phone. Errors carry the route template,
the request id (also in the logs and the `X-Request-ID` header) and, in the API, the tenant id.

## Errors (Sentry, free tier is enough to start)

1. Create a Sentry account and three projects: one Python (API), one Next.js (web) and one React
   Native (the three Expo apps can share it; the app name is in each event's context).
2. Set the DSNs (a DSN is not a secret, but keep them in settings, not in the repository):

| Where | Variable | Value |
|---|---|---|
| API host (Render) | `API_SENTRY_DSN` | the Python project's DSN |
| API host (optional) | `API_SENTRY_TRACES_SAMPLE_RATE` | `0` (default) to `1`; performance traces, costs quota |
| Web (Vercel) | `NEXT_PUBLIC_SENTRY_DSN` | the Next.js project's DSN (also opens the page's CSP to the Sentry host) |
| Web (optional) | `NEXT_PUBLIC_SENTRY_ENVIRONMENT`, `NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE` | `staging` / `production`, `0`..`1` |
| Expo apps (build env) | `EXPO_PUBLIC_SENTRY_DSN` | the React Native project's DSN |

3. Redeploy. Where: `apps/api/app/core/monitoring.py`, `apps/web/src/instrumentation*.ts` and
   `apps/web/src/lib/monitoring.ts`, `packages/app-kit/src/lib/monitoring.ts`.

Readable stack traces for native builds need source-map upload (Sentry's Expo plugin with an auth
token); add it with the first store build.

## Uptime

`.github/workflows/keep-api-awake.yml` checks `/health/ready` (database reachable) and the web app
every 10 minutes during the Israeli day, retrying before it fails; GitHub emails the repository's
watchers when it fails. For production, set the repository variables `UPTIME_API_URL` and
`UPTIME_WEB_URL`, or add a free outside monitor (UptimeRobot or Better Stack) on
`/health/ready` with 24/7 coverage and a phone alert; the workflow's schedule does not run at night
to save the free GitHub minutes.
