# Production: from the day you approve the payment until it runs

Everything here is built as code and **off**. Nothing below has been created, upgraded or paid
for. Do the steps in order; each one says what it costs and how to check it. Staging stays as it
is (see [staging.md](staging.md)); production is a separate set of services and a separate
database. Costs are monthly list prices and move; confirm them on the provider's page before you
click.

## 0. Before you start

- Decide the public addresses (for example `https://<domain>` for the web and
  `https://api.<domain>` for the API). The domain steps are in the go-live checklist.
- Turn on two-step sign-in on every provider account first (GitHub, Supabase, Render, Vercel, the
  domain registrar, Google, Apple, Sentry, UptimeRobot). It is free.
- Generate the secrets on your own machine and keep a copy in a password manager. Never paste
  them in chat, in an issue or in a file in this repository:
  - `API_SECRETS_KEY`: a Fernet key (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
  - `API_ID_HASH_KEY`: a second, different value of the same kind. Setting it from the start means
    a later key rotation never has to re-hash ID numbers.
  - `API_INTERNAL_TOKEN`: a long random value (the same on Render and Vercel).

## 1. Supabase project for production (Pro, about $25)

1. Supabase, New project, region Central EU (Frankfurt), a strong database password. A separate
   project, never the staging one.
2. Settings, Database: copy the **session pooler** connection string (port 5432) with the password.
   This is `API_DATABASE_URL`. It stays in Render only (section 5).
3. Settings, API: copy the project URL and the JWKS address
   `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json` (`API_JWKS_URL`).
4. Auth settings: follow [auth-settings.md](auth-settings.md) (sign-up, email templates, two-step
   sign-in on, redirect addresses = the production web address). With the Pro plan, also turn on
   the leaked-password check (see the go-live checklist, "Switch-on steps that need a paid plan").
5. Settings, Backups: confirm daily backups; for point-in-time recovery see
   [restore-runbook.md](restore-runbook.md).

Check: the project shows "healthy" and the pooler string connects (`psql "<string>" -c "select 1"`
from your machine).

**Connection budget (GL18).** Each API worker keeps up to `API_DB_POOL_SIZE` (5) plus
`API_DB_MAX_OVERFLOW` (10) connections, so the API service can open at most
`WEB_CONCURRENCY` (2) x 15 = **30** connections. The two cron jobs each open a few more while they
run (one worker, same pool settings, so up to 15 each): worst case 30 + 15 + 15 = **60**. Compare
that with the limit for your Supabase compute size (Settings, Database, "Connection pooling" shows
the pooler's client limit; the direct-connection limit is on the compute page) and keep the worst
case at or below about 60% of it. Before adding a second API instance or raising `WEB_CONCURRENCY`,
redo the sum: instances x workers x 15, plus the crons.

## 2. Render Blueprint (API Starter about $7, two cron jobs about $7 each)

[`render.production.yaml`](../../render.production.yaml) defines the API web service
`business-os-api` and the two background jobs.

1. Stop the staging GitHub schedules only if they point at the same database (they should not:
   staging has its own).
2. Render, New, Blueprint, choose the repository, **file name `render.production.yaml`**.
3. Render asks once for each `sync: false` value. Fill them from the table in section 5. Leave the
   optional ones empty until the feature is wanted.
4. Create. The first deploy runs `alembic upgrade head` as the **pre-deploy step**, then starts the
   API. The API container itself never migrates in production (`RUN_MIGRATIONS_ON_START=false`).
5. Auto-deploy is off. A release is a deliberate action: Render, the service, Manual Deploy, or the
   release workflow (section 6).

Check: `https://<api>/health/ready` answers 200 (it also checks the database); the Render deploy
log shows the migration finishing before the service goes live.

## 3. Vercel project for the website (Pro, about $20 per seat)

1. Vercel, Add New Project, import nothing from Git (the repository is private in an organization,
   which the Hobby plan cannot deploy from Git; on Pro you may connect Git, but keep deploys
   manual or by tag as in section 6). Create it empty, or with `vercel link` from your machine.
2. Environment variables (Production), as **sensitive**: `API_INTERNAL_TOKEN`, the API address the
   site calls, the Supabase URL and publishable key. Plus the production switches
   `WEB_ALLOW_INDEXING=true` and, only after the domain and all its subdomains serve HTTPS,
   `WEB_HSTS_INCLUDE_SUBDOMAINS=true` (details: the go-live checklist, "Website headers").
3. Domains: add the production domain; DNS is set at the registrar (the go-live checklist).
4. Note the team id and project id (Project Settings). They go in section 4 as repository
   variables, not secrets.

## 4. GitHub environment `production`

1. Settings, Environments, New environment `production`. Turn on **Required reviewers** (you) and
   restrict it to tags `v*` ("Deployment branches and tags").
2. Secrets in this environment only:
   - `VERCEL_TOKEN`: a token that can deploy the production project only.
   - `RENDER_API_KEY` (optional): lets the release and rollback workflows roll the API back.
   - `RENDER_DEPLOY_HOOK_URL` (optional): the service's Deploy Hook from Render, Settings. When set,
     the release workflow starts the API deploy for the same tag.
3. Repository variables (not secret): `PRODUCTION_VERCEL_ORG_ID`, `PRODUCTION_VERCEL_PROJECT_ID`,
   `PRODUCTION_WEB_URL`, `PRODUCTION_API_URL`; in the environment: `RENDER_SERVICE_ID`,
   `HEALTH_API_URL`, `HEALTH_WEB_URL` (see [releases.md](releases.md)).
4. **Do not add any database connection string to GitHub for production.** The production jobs and
   the migrations run on Render, where the owner connection already lives. The GitHub `staging`
   environment keeps `STAGING_DATABASE_URL` for staging only. A test
   (`apps/api/tests/test_production_as_code.py`) fails if a workflow that uses the `production`
   environment mentions a database URL.

## 5. Variables, in one place

| Variable | Where | Value |
|---|---|---|
| `API_ENVIRONMENT` | Render (set in the file) | `production` |
| `RUN_MIGRATIONS_ON_START` | Render (set in the file) | `false` |
| `API_DATABASE_URL` | Render | Supabase session pooler string |
| `API_JWKS_URL` | Render | the JWKS address from section 1 |
| `API_SECRETS_KEY`, `API_SECRETS_KEYS`, `API_ID_HASH_KEY` | Render (API and both jobs) | see section 0 and [key-rotation.md](../runbooks/key-rotation.md); set `API_SECRETS_KEYS` to the same single key at first |
| `API_INTERNAL_TOKEN` | Render and Vercel | the same value in both |
| `API_WEB_URL`, `API_API_URL`, `API_CORS_ORIGINS` | Render | the public addresses; the origins as a JSON list, no localhost |
| `API_MFA_REQUIRED_FROM` | Render | a date 14 days after go-live (`YYYY-MM-DD`) |
| `API_ANTHROPIC_API_KEY`, `API_SUPABASE_URL`, `API_SUPABASE_SERVICE_KEY`, `API_SENTRY_DSN` | Render, optional | when the feature is wanted (see the go-live checklist) |
| `WEB_ALLOW_INDEXING`, `WEB_HSTS_INCLUDE_SUBDOMAINS` | Vercel | section 3 |
| `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_KEY` | EAS environment `production` | section 7 |

The API refuses to start in production if the first group of settings is missing or still points at
localhost (`missing_production_settings` in `apps/api/app/core/config.py`).

## 6. Releases and rollback

Full guide: [releases.md](releases.md).

- A release is a tag on `main`: `git tag v1.0.0 && git push origin v1.0.0`.
- [`release.yml`](../../.github/workflows/release.yml) writes the GitHub Release notes.
  [`deploy-web-production.yml`](../../.github/workflows/deploy-web-production.yml) runs from that
  tag only, waits for your approval in the `production` environment, records the release, deploys
  the website and, when the hook secret exists, starts the API deploy for the same commit. It
  refuses a tag that is not on `main`, checks the health addresses afterwards and rolls back when
  they fail.
- Rollback: Actions, **Roll back** ([`rollback.yml`](../../.github/workflows/rollback.yml)), or by
  hand in the Render and Vercel dashboards. The database is not rolled back; migrations expand
  first and contract one release later.
- Alert hooks (slice GL13): the uptime monitor points at `/health/ready` and at the web home page;
  the Render health check already uses `/health/ready`. See [on-call.md](on-call.md).

## 7. Mobile apps

[`apps/client-app/eas.json`](../../apps/client-app/eas.json) build profile `production` reads the
EAS **environment** `production`. In expo.dev, Project, Environment variables, create the three
`EXPO_PUBLIC_*` variables there with the production addresses (the publishable key is public by
design; no secret goes in an app). Android needs no paid account; iOS needs the Apple Developer
program (about $99 a year), see [../mobile-builds.md](../mobile-builds.md).

## 8. Who can reach what

| System | Who | How | Notes |
|---|---|---|---|
| Supabase production | Owner | Account with two-step sign-in | Claude can use the Supabase tools only when you grant it for the session; revoke after |
| Render production | Owner | Account with two-step sign-in | Holds the only copy of the owner database string next to the password manager |
| Vercel production | Owner | Account with two-step sign-in | Deploy token lives only in the GitHub `production` environment |
| GitHub `production` environment | Owner approves | Required reviewer | Claude never approves its own release |
| Password manager | Owner | | Copies of all keys in section 0 |
| EAS / App stores | Owner | Account with two-step sign-in | |

Review this table whenever someone is added. Remove access the day it is no longer needed.

## 9. First-hour check

1. `https://<api>/health/ready` is 200 and `https://<domain>` loads.
2. Sign up a test business, sign out, sign in (with the authenticator code if the date has passed).
3. Create a booking and open a document.
4. Render, the two cron services, "Trigger Run": both finish and appear in `app.job_runs`.
5. Take a manual backup, then plan the restore drill ([restore-runbook.md](restore-runbook.md)).
6. Remove or change every demo password; delete test businesses.
