# Launch-readiness review (October 2026)

> **Status (go-live, October 2026):** items fixed since this review are tracked with ✅ / 🟡 / 🔴 and their pull request in the [go-live scorecard](go-live-readiness-2026-10.md). Where the two disagree, the scorecard is current.

_2026-10-10_ · Whole-repository review before the first real customers: architecture and file
layout, API, database and migrations, web, Expo apps, shared packages, CI, deployment,
scheduled jobs, observability, security, performance, tests and cost. It builds on the
[architecture review](architecture-2026-10.md), the [security review](security-2026-10.md) and
the [privacy review](privacy-2026-10.md); nothing fixed there is repeated here.
Owner's summary in Hebrew: [launch-readiness-2026-10.he.md](launch-readiness-2026-10.he.md).

This is a read-only review: no code changed. Every item is written so a later thread can pick it
up alone: where, why, the fix, how to know it is done, size and which model should do it
(Opus for security, tenant isolation, schema and architecture; Sonnet for the rest, per
[`docs/claude-code.md`](../claude-code.md)).

## Verdict

The product core is in good shape for a beta with friendly businesses: tenant isolation is
enforced in the database (RLS on every table, membership-based context, tested), money and time
follow the principles, every outside service sits behind a swappable provider, and there are
355 API tests plus 34 end-to-end flows. **It is not ready for paying customers yet.** What is
missing is mostly around the code rather than in it: there is no production environment (only
staging on free tiers), no logging or error tracking, scheduled jobs run on GitHub's cron, which
is visibly unreliable, a few security defaults fail open, the AI has no cost ceiling, and files
are stored inside Postgres. All of it is fixable in roughly two to three weeks of focused
slices, in the order at the end.

Severity: **P0** blocks taking paying customers · **P1** within the first month of operation ·
**P2** hygiene, do when touching the area. Size: **S** ≤ half a day · **M** 1-2 days · **L** 3+ days.

## What is sound (keep it)

- Tenant context per transaction (`app/core/db.py`): `SET LOCAL ROLE app_api` and
  transaction-local settings re-applied on every `after_begin`, so a commit never leaves a session
  unrestricted. Support access is `READ ONLY` at the database level and audited (`app/api/deps.py`).
- Database guards: `test_database_security.py` checks RLS on every table, pinned `search_path` on
  SECURITY DEFINER functions and that public roles can't reach app tables.
- Concurrency: booking capacity locks the session row (`FOR UPDATE`, `app/api/bookings.py`);
  court double-booking is refused by an exclusion constraint.
- Generated artifacts are drift-checked in CI: the API client (`ci.yml`) and the verticals
  catalog copies (`packages/verticals/test/catalog.test.ts`); translation keys have a parity test.
- Regions are aligned: Vercel `fra1` (`apps/web/vercel.json`), Render Frankfurt, Supabase
  `eu-central-1`.
- Providers (payments, invoicing, messaging, email, AI, storage) are interfaces with contract
  tests (`test_provider_contracts.py`), so going live is configuration plus one class per vendor.

## P0: before paying customers

### P0-1 · There is no production environment
- **Where:** `render.yaml` (`plan: free`), `.github/workflows/deploy-web.yml` (deploys "production"
  using the `staging` environment), one Supabase project (free tier, the only one in the account).
- **Why:** free Render sleeps after 15 idle minutes (cold starts and 502s); free Supabase has no
  usable backups or point-in-time restore, pauses on inactivity, caps the database at 500 MB and
  can't enable leaked-password protection (advisor warning today); Vercel Hobby is for
  non-commercial use only. Demo data, test accounts and real customers would share one database.
- **Fix:** a separate production stack: Supabase Pro project (daily backups, PITR add-on
  optional), Render Starter web service, Vercel Pro (or move the web to another host), a
  `production` GitHub environment with its own secrets, its own Supabase Auth settings and
  templates, and `render.yaml` with a second service. Staging stays as is for demos.
- **Done when:** production URLs serve from their own database; a restore of last night's backup
  into a scratch project has been tried once and written down in `docs/deploy/production.md`.
- **Size:** M (plus the owner opening accounts) · **Model:** Sonnet (Opus reviews the env split).
- **Owner decision needed:** yes (cost, see the cost section).

### P0-2 · Scheduled jobs run on GitHub's cron, which skips most runs
- **Where:** `.github/workflows/emails-staging.yml` (hourly), `jobs-staging.yml` (daily),
  `keep-api-awake.yml` (every 10 minutes).
- **Evidence:** on 2026-10-10 the every-10-minutes keep-alive ran 4 times in the day instead of
  ~108; the hourly email job ran 6 times in about 26 hours. GitHub delays and drops scheduled
  runs under load. Notification emails therefore arrive hours late, and the keep-alive does not
  keep the API awake.
- **Also:** these jobs hold the database owner's connection string as a GitHub secret, so the
  widest credential in the system lives in CI.
- **Fix:** run jobs next to the API: Render Cron Jobs built from the same image
  (`python -m app.jobs <job>`), with the owner URL only in Render. Keep the GitHub workflows for
  staging-by-hand only (`workflow_dispatch`). Every job logs a start/end line and its counts, and
  a failed run alerts (P0-3). Delete `keep-api-awake.yml` once the API is on a paid plan.
- **Done when:** a job's last successful run is visible and alerts fire when one is missed.
- **Size:** S-M · **Model:** Sonnet.

### P0-3 · No logging, error tracking or alerting anywhere
- **Progress:** ✅ (1) API structured JSON logs, request ids, stable 500 body, slow-query log (this PR). Still open: (2) error tracker and (3) uptime monitor (need an account), (4) ✅ web error pages (error, global-error, not-found; PR 2).
- **Where:** no file under `apps/api/app` imports `logging`; no Sentry/OpenTelemetry in the API,
  the web app or the Expo apps; `apps/web/src/app` has no `error.tsx`, `global-error.tsx` or
  `not-found.tsx`.
- **Why:** when something breaks for a customer nobody will know, and there is no trail to find
  out why. A cold-started or failing API shows Next's default crash page (English, unbranded).
- **Fix:** (1) API: structured JSON logs with a request id, tenant id and user id (never personal
  data), an exception handler that logs and returns a stable error body, slow-query logging above
  a threshold. (2) Error tracking (Sentry free tier or similar) in API, web (server and client)
  and the three apps, with personal data scrubbed. (3) Uptime check on `/health/ready` from an
  outside monitor (free tier) with alerts to the owner. (4) Web `error.tsx`, `global-error.tsx`
  and `not-found.tsx` with translated texts and a Try again button.
- **Done when:** a forced error shows in the tracker with its request id; stopping the API pages
  the owner within 5 minutes; the web shows a branded, translated error page.
- **Size:** M · **Model:** Sonnet.

### P0-4 · Security settings fail open when the environment is not set
- **Where:** `apps/api/app/core/config.py` (`environment: str = "local"`),
  `app/core/signed_links.py:23`, `app/providers/secrets.py:26`, `rate_limits_on`.
- **Why:** if `API_ENVIRONMENT` is missing in a deployment (a new service, a typo), the API
  silently signs file links and encrypts provider secrets with the public development key (it is
  in the repository), turns rate limits off and answers AI in demo mode. The security review fixed
  the missing-key case, but the default environment re-opens it.
- **Fix:** no default for `environment` outside a local `.env`; refuse to start when it is unset,
  or when it is `local`/`test` while `database_url` points anywhere but localhost. Accept only a
  fixed set (`local`, `test`, `staging`, `production`).
- **Done when:** a test starts the app with a remote-looking URL and no environment and expects a
  startup error.
- **Size:** S · **Model:** Opus.

### P0-5 · Rate limits can be bypassed with a forged `X-Forwarded-For`
- **Where:** `app/core/rate_limit.py` `client_address` (takes the **first** forwarded address),
  `Dockerfile` (`--proxy-headers --forwarded-allow-ips='*'`), `apps/web/src/lib/api.ts`
  `forwardedFor`.
- **Why:** anyone can call the API directly with `X-Forwarded-For: <random>`; the proxy appends
  the real address, but the limiter counts the first one, so every request looks like a new
  visitor. Public forms, inquiry and quote endpoints lose their limits. `forwarded-allow-ips='*'`
  also lets any caller set the scheme and client address uvicorn reports.
- **Fix:** count the address the hosting proxy saw (the right-most entry it appended, or the
  host's own client-IP header), and accept a visitor address from the web server only when it
  also sends a shared secret header (`API_INTERNAL_TOKEN`) that only Vercel knows. Restrict
  `forwarded-allow-ips` to the proxy.
- **Done when:** a test proves that a spoofed header from outside does not reset the count, and
  that the web server's forwarded address still counts per visitor.
- **Size:** S-M · **Model:** Opus.

### P0-6 · The AI assistant has no cost ceiling (before connecting the key, #50)
- **Where:** `app/ai/gateway.py` (`max_tokens=16000`), `app/ai/assistant.py` (`MAX_STEPS = 8`),
  `app/core/config.py` (`ai_model = "claude-opus-5-5"`).
- **Why:** usage is recorded but never enforced. One busy business, a loop of tool calls or abuse
  of a stolen session can spend without limit, on the most expensive model, through a call that
  blocks an API thread for minutes.
- **Fix:** (1) a monthly AI allowance per business from its plan (soft warning at 80%, hard stop
  at 100% with an upgrade offer, like X17 for messages), checked before each model call from the
  usage events; (2) a per-user rate limit on `/assistant` messages; (3) default to a cheaper model
  for everyday Q&A with an explicit opt-in for the bigger one; lower `max_tokens`; a request
  timeout; (4) a platform-wide daily spend alarm in the console.
- **Progress:** ✅ (1) monthly allowance per AI module, warnings at 80% and 100%, new questions refused with `ai_limit_reached` (PR #184; amounts provisional, `AI_CREDITS_INCLUDED`, decision X33). ✅ (2) per-user rate limit (6/min, 60/hour, `ai_rate_limited`), (3) cheap default model `claude-haiku-5-5` escalating to `claude-sonnet-5-5` after 3 model calls in one message, `max_tokens` 4096, 60 s timeout, (4) daily platform AI spend alarm in the console (`/platform/ai-spend`, threshold 2,000 credits). All limits are settings (`API_AI_*`); decision X34. **P0-6 complete.**
- **Done when:** a test exhausts a tenant's allowance and the next message is refused with a
  clear code; the console shows AI spend per business.
- **Size:** M · **Model:** Opus designs the allowance (it touches billing and modules), Sonnet builds.
- **Owner decision needed:** allowance per plan.

### P0-7 · Files are stored inside Postgres
- **Where:** `app/providers/storage.py` (only the `database` provider exists), documents up to
  10 MB (`app/api/documents.py`), logos, covers and avatars.
- **Why:** the plans sell 2 GB / 20 GB / 100 GB of storage per business (#104), which cannot live
  in a Postgres row store: it bloats the database and backups, slows restores, and costs database
  prices per GB. Serving files also streams them through the API process.
- **Fix:** an S3-compatible storage provider (Supabase Storage or any S3 bucket), private bucket,
  short-lived signed download URLs, a one-time migration job that moves existing bytes out, and
  `storage_used` kept as today. Keep `database` for local development.
- **Done when:** a new document lands in the bucket, the row holds only the key, erasure deletes
  the object (privacy review), and the quota numbers still match.
- **Size:** M · **Model:** Opus for the design and data move, Sonnet for the provider.

### P0-8 · Auth settings on the hosted project are not managed from the repository
- **Progress:** ✅ checklist in `docs/deploy/auth-settings.md` (PR 4); applying settings from CI is still open.
- **Where:** `supabase/config.toml` says `otp_length = 6`; the hosted project sent an 8-digit code
  (2026-10-10). Email templates and redirect URLs are also set by hand.
- **Why:** every new environment (production) will drift the same way, and sign-in is the first
  thing a customer touches.
- **Fix:** one source of truth: apply auth settings with `supabase config push` (or the
  management API) per environment from CI, or at least a checklist in `docs/deploy/` plus a smoke
  test that signs in with a code on staging after each change.
- **Size:** S · **Model:** Sonnet.

### P0-9 · Legal and account basics
- **Where:** privacy review items 2-4; `app/jobs.py:339` (deletion of a departed business waits
  for an account-closing flow that does not exist).
- **Fix:** a privacy notice and processing agreement for businesses, the sub-processor list, an
  account-closing flow (owner closes the business; data deleted after 90 days per X20), terms of
  use with a cancellation clause, cookie notice if analytics are added.
- **Size:** M · **Model:** Sonnet (the texts need the owner's and possibly a lawyer's review).

## P1: first month of operation

### P1-1 · Blocking database calls inside `async` endpoints
- **Progress:** ✅ All seven handlers are plain `def` (the webhook reads its body in an async dependency); `tests/test_concurrency.py` fails if any route handler becomes `async def`.
- **Where:** `app/api/documents.py:216` and `:293`, `app/api/settings.py:91` and `:154`,
  `app/api/people.py:21`, `app/api/client_import.py:71`, `app/api/webhooks.py:21`.
- **Why:** these are `async def` but use the synchronous SQLAlchemy session, so while one 10 MB
  upload is written to the database every other request on that worker waits. FastAPI runs plain
  `def` endpoints in a thread pool; `async def` ones run on the event loop.
- **Fix:** make them plain `def` and read the upload with `file.file.read()` (or keep `async`
  and push the database work to `run_in_threadpool`). Add a ruff/pytest guard that no `async def`
  route takes a session dependency.
- **Size:** S · **Model:** Sonnet.

### P1-2 · One worker, default pool, no pooler settings
- **Progress:** ✅ `WEB_CONCURRENCY` workers (default 2) in the Dockerfile; pool size, overflow, timeout and recycle are `API_DB_*` settings; prepared statements off (works with Supavisor transaction mode, port 6543); at most `API_AI_MAX_CONCURRENT_CALLS` (8) model calls per worker, the rest get 429 `ai_busy`. Not done: load test, and a shared store for the per-process rate limits (they now count per worker).
- **Where:** `Dockerfile` CMD (single uvicorn process), `app/core/db.py`
  (`create_engine(..., pool_pre_ping=True)`: 5 connections + 10 overflow).
- **Why:** one Python process handles everything; the thread pool (40) can outrun the 15
  connections, and a slow AI call holds a thread. Supabase limits direct connections; moving to
  its pooler in transaction mode needs psycopg's prepared statements off.
- **Fix:** run 2-4 workers (gunicorn with uvicorn workers, sized to the instance), set
  `pool_size`/`max_overflow`/`pool_timeout` from settings, connect through Supavisor with
  `prepare_threshold=None` (the per-transaction `SET LOCAL` context already works in transaction
  mode), and move the assistant's model calls off the request thread or give them their own limit.
  Load-test one busy tenant page (schedule week, 4 branches) before and after.
- **Size:** M · **Model:** Opus.

### P1-3 · Migrations run on every container start, and in a workflow too
- **Progress:** ✅ CI test fails on more than one head, duplicate numbers or a file name that differs from its revision (PR 4). The pre-deploy step needs the paid Render plan.
- **Where:** `Dockerfile` CMD (`alembic upgrade head && uvicorn ...`),
  `.github/workflows/migrate-staging.yml`.
- **Why:** two mechanisms for one job; with more than one instance or worker each start races to
  migrate; a failing migration crash-loops the service. Duplicate revision numbers already
  happened once (two `0058` files, renumbered in #139).
- **Fix:** migrate in a pre-deploy step (Render `preDeployCommand` on a paid plan) and start the
  server without it. In CI: fail when `alembic heads` has more than one head or two files share a
  number prefix, and run `alembic upgrade head` on an empty database (already implicit in tests;
  make it explicit) plus on a copy of staging's schema before merging a migration.
- **Size:** S · **Model:** Sonnet.

### P1-4 · Indexes and RLS policies flagged by Supabase's advisor
- **Evidence (2026-10-10, staging):** 55 foreign keys without a covering index, 41
  multiple-permissive-policy warnings, 25 unused indexes, `btree_gist` in `public`.
- **Why:** several unindexed keys sit on hot paths of the client card and boards:
  `client_notes (tenant_id, client_id)`, `messages (tenant_id, client_id)` and `(tenant_id,
  lead_id)`, `leads (tenant_id, client_id)`, `reviews (tenant_id, client_id)`, `shifts
  (tenant_id, location_id)`, `session_series (tenant_id, location_id)`, `entitlement_freezes
  (tenant_id, entitlement_id)`, `quote_lines (tenant_id, quote_id)`. Deleting a client or a
  location scans these tables. Two permissive policies per action (a `_client` and a `_tenant`
  policy) are both evaluated for every row of hot tables (`bookings`, `sessions`, `clients`,
  `tenants` has four).
- **Fix:** one migration adding the composite indexes above (skip `created_by`-style audit keys
  that are never filtered on); merge each table's client and tenant policies into one policy per
  action with `OR`, keeping semantics identical (prove it with the existing isolation tests plus
  the new matrix in P1-8). Leave unused indexes until real traffic shows what is used.
- **Size:** M · **Model:** Opus (RLS rewrite), Sonnet for the indexes alone.

### P1-5 · Lists without a limit
- **Where:** routers that return lists with no `limit` and no required date window:
  `resources.py` (9 lists), `appointments.py` (8), `reports.py` (5), `shifts.py`,
  `shift_planning.py`, `dependents.py`, `locations.py`, `integrations.py`, `services.py`,
  `promo_codes.py`, `stations.py`, `businesses.py`, `privacy.py`.
- **Why:** a network with four branches and a year of history makes some of these grow with
  time; a single call can return thousands of rows and render slowly on phones.
- **Fix:** time-based lists require a bounded window (max 92 days); catalog lists get a hard cap
  with paging; reports aggregate in SQL. Check each against the web and app callers.
- **Size:** M · **Model:** Sonnet.

### P1-6 · The web ships every translation to every page
- **Where:** `apps/web/src/app/layout.tsx:31` (`<NextIntlClientProvider>` without `messages`),
  `packages/i18n/messages/he.json` (215 KB) and `en.json` (177 KB).
- **Why:** next-intl passes all messages to client components by default, so each page carries
  the whole catalog (marketing, console, every module) in its payload.
- **Fix:** pass only the namespaces client components use (`pick(messages, [...])` per layout:
  marketing, app, console), and split `he.json`/`en.json` per area so the Expo apps also import
  only theirs.
- **Done when:** the sign-in page's HTML/RSC payload drops by the size of the catalog.
- **Size:** M · **Model:** Sonnet.

### P1-7 · Per-request overhead and `LiveRefresh`
- **Where:** `app/api/deps.py` `get_tenant_context` (role switch, two `set_config`, membership
  lookup, branch check: about five round trips before the endpoint's own queries);
  `apps/web/src/components/live-refresh.tsx` (every 60 s, a full server re-render of the page with
  all of its API calls, per open tab).
- **Fix:** one SQL function that sets the context and returns role, permissions and branches in
  a single call; `LiveRefresh` at 3-5 minutes plus refresh on focus, or a cheap "changed since"
  endpoint the page polls before refreshing.
- **Size:** S-M · **Model:** Opus for the context function (tenant isolation), Sonnet for the web.

### P1-8 · Tenant and branch isolation need a test matrix, not examples
- **Progress:** 🟡 Part 3 done (#187): branch matrix for a member kept to one branch across sessions, bookings, clients, series, shifts, stations, templates, hours and publish (`tests/test_branch_access.py`); it found and fixed a real hole: by-id reads and writes ignored the branch limit. Part 2 done in spirit (#187): `tests/test_critical_paths.py` calls every route without a login and fails unless it is on the public list. Part 1 done: `tests/test_tenant_matrix.py` seeds seven businesses and, for every table with a `tenant_id` (unseeded ones get a synthetic row), proves an outsider claiming the business sees, updates, deletes and inserts nothing, while its owner sees all rows; a new table is covered automatically, and disabling RLS on a table makes it fail. Still open: by-id branch checks on the client sub-resources (notes, documents, health declarations, dependents, receipts, quotes).
- **Where:** `tests/test_tenant_isolation.py` (deep checks for `clients` only),
  branch scoping in `app/api/deps.py` `set_branch` (#64).
- **Why:** each new table and route adds a way to get isolation wrong; branch-limited staff are
  filtered in lists through `app.in_branch`, but reads and writes by id (a client, session or
  shift of another branch) are not covered by tests.
- **Fix:** (1) a parametrized test that, for every table with `tenant_id`, inserts a row as
  tenant A and proves tenant B can't select, update or delete it; (2) a route scan that fails when
  a route has neither a tenant/session dependency nor an entry in an explicit public allowlist;
  (3) a branch matrix for a branch-limited member across get/update by id. Fix what it finds.
- **Size:** M · **Model:** Opus.

### P1-9 · End-to-end checks and Expo apps are outside CI
- **Where:** `e2e/` (34 flows, run by hand), `apps/*-app/package.json` (typecheck only; no lint,
  no tests, no `expo export` in CI).
- **Fix:** a nightly (or `e2e` label) workflow that starts Supabase, the API and the web and runs
  `dod.py` and the crawl; add `expo export --platform web` for the three apps to CI so a broken
  import fails the PR; ESLint for the apps.
- **Size:** M · **Model:** Sonnet.

### P1-10 · Mobile apps: token storage, store builds, push
- **Where:** `packages/app-kit/src/lib/supabase.ts` (session in `AsyncStorage`), no `eas.json`
  in any app, no `expo-notifications`, bundle ids `com.businessos.*` while the brand is MyBiz.
- **Fix:** keep the session in `expo-secure-store` on iOS/Android (AsyncStorage only on web);
  `eas.json` profiles (development, preview, production) per app with OTA update channels;
  push notifications for reminders (cheaper and more reliable than SMS/WhatsApp); decide final
  bundle ids before the first store upload (they can never change); crash reporting (P0-3).
- **Size:** L · **Model:** Sonnet. **Owner decision:** bundle ids and store accounts.

### P1-11 · Dependency and secret hygiene automation
- **Progress:** ✅ Dependabot (weekly, grouped; PR 3). CodeQL and secret scanning with push protection are paid on a private repository (GitHub Advanced Security) - left for the owner's decision.
- **Where:** `.github/` has no `dependabot.yml`, no CodeQL, no secret-scanning config.
- **Fix:** Dependabot (or Renovate) weekly for npm, uv, GitHub Actions and Docker with grouped
  updates; CodeQL for Python and TypeScript; enable GitHub secret scanning and push protection.
- **Size:** S · **Model:** Sonnet.

## P2: hygiene (when touching the area)

| # | Finding | Where | Fix | Size · Model |
|---|---|---|---|---|
| P2-1 ✅ | Status docs drift: "In progress" holds ~30 finished items, the crop/palette entry appears three times (as X27 and X28), the English and Hebrew boards differ (the Expo web addresses are only in Hebrew), DECISIONS has no X29 and X28 listed before X27 | `docs/STATUS.md`, `docs/STATUS.he.md`, `docs/DECISIONS.md` | Move finished items to a "Done" section (or `docs/CHANGELOG.md`), keep "In progress" to what is actually open, mirror both languages, note X29 as skipped | S · Sonnet |
| P2-2 | Large modules mixing HTTP, SQL and rules | `app/ai/tools.py` (814 lines), `app/api/schedule.py` (766), `app/seed/business.py` (711), `app/api/resources.py` (624), `apps/web/.../start-wizard.tsx` (731), `apps/business-app/src/app/session/[id].tsx` and `client/[id].tsx` (500+) | Continue X18: routers keep validation and permissions, SQL moves to the domain package (`schedule/`, `commerce/`…); split the AI tools per domain; split big screens into sections. Only when a slice touches the file | L (gradual) · Sonnet |
| P2-3 ✅ | 60+ routers registered by hand in one list | `app/main.py` | Each module exports its routers; `main.py` loops over one registry. A forgotten router can't happen | S · Sonnet |
| P2-4 ✅ | `.claude/skills` vendors 143 third-party skill files into the repo | `.claude/skills/` | Keep only project-specific skills in the repo; install the rest per user (`skills-lock.json` already lists them) | S · Sonnet |
| P2-5 | `btree_gist` installed in `public` | migration that created the exclusion constraint | Move to `extensions` schema in a migration (check the constraint still resolves) | S · Opus |
| P2-6 | Keep-alive and hourly cron for a free tier | `keep-api-awake.yml`, `emails-staging.yml` | Remove after P0-1/P0-2 | S · Sonnet |
| P2-7 | Unused indexes (25 on staging) | advisor | Revisit after a month of production traffic | S · Sonnet |
| P2-8 | Demo seed code and `POST /tenants/sample` ship in the production image | `app/seed`, `app/api/samples.py` | Confirm the sample endpoint is meant for production (sample business for new owners); keep the seed CLI out of reach of the API role | S · Sonnet |

## Cost at launch (monthly, estimated)

| Item | Today | At launch |
|---|---|---|
| Database and auth (Supabase) | Free | Pro ≈ $25 (backups, no pausing, leaked-password check) |
| API (Render) | Free (sleeps) | Starter ≈ $7, plus cron jobs ≈ $1-3 |
| Web (Vercel) | Hobby (non-commercial) | Pro ≈ $20, or another host |
| Errors and uptime | none | free tiers (Sentry, an uptime monitor) |
| Email | Gmail SMTP (personal, daily cap) | Resend free → ≈ $20 at volume, on the product's domain |
| Domain | none | ≈ $15 per year |
| Stores | none | Apple $99 per year, Google $25 once |
| AI | demo | usage, capped per business (P0-6) |

Roughly **$55-75 a month plus AI usage** before the first payment provider fees. GitHub Actions
minutes stop mattering once jobs leave GitHub (P0-2).

## Order of work

Each line is one thread and one PR, short enough for a fresh thread (CLAUDE.md).

| Wave | Items | Model | Depends on |
|---|---|---|---|
| 0 · Owner | Approve the production stack and its cost (P0-1), AI allowance per plan (P0-6), final bundle ids (P1-10), domain and email provider (#48) | - | - |
| 1 · Security | P0-4 fail-closed config · P0-5 forwarded-address limits · P1-8 isolation matrix | Opus | - |
| 2 · Operations | P0-3 logging, errors, uptime, web error pages · P0-2 jobs on Render cron · P1-3 migrations pre-deploy + CI checks · P1-11 Dependabot/CodeQL | Sonnet | P0-2 needs the paid Render plan for cron |
| 3 · Production | P0-1 production stack, backups and a restore drill · P0-8 auth settings from the repo | Sonnet (Opus reviews) | Wave 0 |
| 4 · Data and speed | P1-1 async endpoints · P1-4 indexes, then merged policies · P1-2 workers and pooler · P1-5 bounded lists · P1-7 request context, LiveRefresh · P1-6 translation payload | Opus for P1-2/P1-4 policies/P1-7 context; Sonnet for the rest | Wave 1 for policy changes |
| 5 · Files and AI | P0-7 object storage · P0-6 AI allowance, then connect the key (#50) | Opus designs, Sonnet builds | Wave 0 |
| 6 · Apps and legal | P1-10 secure storage, EAS, push · P1-9 e2e and Expo in CI · P0-9 legal and account closing | Sonnet | Wave 3 |
| 7 · Hygiene | P2 table | Sonnet | any time |

When a wave's PRs are merged, update `docs/STATUS.md` and `docs/STATUS.he.md`, and mark the item
here with ✅ and the PR number, as the earlier reviews do.
