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

   Optional: `API_SENTRY_RELEASE` (defaults to the commit Render deployed) and, on the web,
   `NEXT_PUBLIC_SENTRY_RELEASE` (the commit SHA) tag every event with the version that produced it.
3. Redeploy. Where: `apps/api/app/core/monitoring.py`, `apps/web/src/instrumentation*.ts` and
   `apps/web/src/lib/monitoring.ts`, `packages/app-kit/src/lib/monitoring.ts`.

Readable stack traces for native builds need source-map upload (Sentry's Expo plugin with an auth
token); add it with the first store build.

## Alerts to your phone

When a background job **fails** (the first failure after a success) or is **late** (the daily
`check-jobs` run), the API alerts every active MyBiz owner (console team, level owner or primary
owner): a push through the MyBiz app on the phone they signed in on, then an email. A job that keeps
failing alerts once; the daily check reminds while it stays broken. No account is needed for the
push (Expo's service); the email needs `EMAIL_PROVIDER` as for the other mail (see
`docs/integrations.md`). An owner gets the push after signing in to the app on their phone once
(that registers the phone).

Where: `apps/api/app/messaging/alerts.py` (recipients and delivery), `apps/api/app/jobs/`
(`run_job` failure alert, `check-jobs`, `test-alert`), `.github/workflows/check-jobs-staging.yml`.

**Check it works** (a manual step, do it once after signing in on the phone): GitHub → Actions →
"Send a test alert (staging)" → Run workflow. The push and the email should arrive within a minute.
The run fails when nobody could be reached.

## System health page

Console → **System health** (`/platform/health`, needs the usage permission): the latest run of
every background job (late and failing ones in red), messages and emails waiting, messages that
failed in 24 hours, database size, AI credits today against the daily alarm, response times per
route (median and p95) and the last 20 crashes with their request id. Search that id in the host's
logs to see the whole request. Job and queue numbers come from the database
(`app.platform_health()`, migration 0119); timings and crashes are the API process's own memory and
reset when it restarts (`apps/api/app/core/metrics.py`). CPU and memory stay in the Render and
Supabase dashboards.

## Uptime

`.github/workflows/keep-api-awake.yml` checks `/health/ready` (database reachable) and the web app
every 10 minutes during the Israeli day, retrying before it fails; GitHub emails the repository's
watchers when it fails. For production, set the repository variables `UPTIME_API_URL` and
`UPTIME_WEB_URL`, or add a free outside monitor (UptimeRobot or Better Stack) on
`/health/ready` with 24/7 coverage and a phone alert; the workflow's schedule does not run at night
to save the free GitHub minutes.

### Outside monitor and public status page (about 10 minutes, free)

1. Create a free UptimeRobot account (or Better Stack). Install their phone app and allow its
   push notifications: that is the alert for "the whole API is down", which the API cannot send
   about itself.
2. Add an HTTP(s) monitor on `https://<api host>/health/ready`, interval 5 minutes, alert contact
   your phone (push) and email. Add a second one on the web address.
3. Create a status page from the two monitors in the same tool. Copy its public address.
4. Set `NEXT_PUBLIC_STATUS_URL` (Vercel, an `https://` address) and redeploy the web app. The
   "System status" link then appears in the site footer and under the support settings of a
   business; until it is set, the links are hidden.
