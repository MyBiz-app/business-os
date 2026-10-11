# On-call routine

For a one-person team today: what to watch, when to act, and how to run an incident. The alerting
tools (error tracking, uptime check) are go-live item B3; this document says what they should
page on, and what to do by hand until they exist.

## What to watch

| Signal | Where | Healthy |
|---|---|---|
| API up | `GET /health/ready` on the API (checks the database) | 200. Add an external uptime check (free tier) at 1-minute or 5-minute interval, alerting the owner by email/push |
| Web up | The web home page and `/sign-in` | 200 |
| Errors | API logs in Render (JSON, with `request_id`; the same id is returned in `X-Request-ID`), Vercel runtime logs | No spike of 5xx |
| Jobs | GitHub Actions: `jobs-staging`, `jobs-hourly-staging`, `emails-staging` | Green runs. A red run means reminders and emails did not go out |
| Database | Supabase dashboard: connections, disk, CPU | Connections under the limit (workers × pool size, see [staging.md](staging.md)) |
| Cost | AI credit caps per plan; Render/Vercel/Supabase usage | Alerts at 80%; Vercel Hobby allows 100 deployments a day |

## Severity

| Level | Meaning | Action |
|---|---|---|
| SEV1 | Site or API down, sign-in broken for everyone, data loss or exposure | Drop everything; update the status page within 15 minutes |
| SEV2 | One feature broken for many, jobs failing, email down | Same day |
| SEV3 | One customer, cosmetic | Normal queue ([support](support.md)) |

## Run an incident

1. **Acknowledge.** Note the start time and what was reported.
2. **Triage** (5 minutes): is `/health/ready` OK? Did a deploy just go out (Render deploys, Vercel
   deployments, GitHub Actions)? Is Supabase or Render having a provider outage?
3. **Mitigate first, then fix.** Fastest safe options in order:
   - Roll back the last deploy (Render: redeploy the previous successful deploy; Vercel: promote
     the previous deployment).
   - Turn off the broken provider adapter (every outside service is behind a swappable provider and
     can be disabled by config).
   - If data is damaged: stop writes and follow the [restore runbook](restore-runbook.md).
4. **Communicate.** Status page (when it exists) and, for affected businesses, one email: what
   happened, what is affected, what we are doing, when the next update comes.
5. **Resolve** and confirm with the smoke test (sign in, open schedule, book, open a document).
6. **Write the note** within two days, in `docs/incidents/YYYY-MM-DD-title.md`: timeline, cause,
   impact, what we changed so it does not repeat. Blameless.

## Suspected data exposure

1. Contain: revoke the exposed key/token, rotate secrets (Render, Vercel, GitHub environments, and
   `API_INTERNAL_TOKEN`), disable the affected endpoint if needed.
2. Establish what, whose and when from the audit log and request-id logs.
3. Notify: businesses affected without undue delay; the supervisory authority within 72 hours where
   GDPR applies; the Israeli Privacy Protection Authority where Israeli law applies. Get legal
   advice before sending.
4. Record it in the incident note.

## Routine checks

| When | What |
|---|---|
| Daily (2 minutes) | Glance at the Actions tab for red job runs and the uptime check |
| Weekly | Dependabot/CodeQL alerts; Supabase advisors (security and performance); backups listed as successful |
| Monthly | Cost vs plan; AI caps; rotate nothing unless needed, but check secret ages |
| Quarterly | Restore drill ([runbook](restore-runbook.md)); review this document |

## Contacts

Fill in before go-live and keep outside the repository if they are personal numbers.

| Role | Who | How |
|---|---|---|
| Owner / primary on-call | Adir | _phone / email in the password manager_ |
| Backup | _none yet_ | |
| Hosting support | Render, Vercel, Supabase | Their dashboards' support forms (paid plans get faster answers) |
