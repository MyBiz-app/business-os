# Go-live readiness review (2026-10-10)

Purpose: a full architecture and file-structure review, written so an Opus or Sonnet thread can
execute it slice by slice. Goal: be sure the project is ready to go live for real businesses.

**How this was done.** A static scan of the repo at `main` (commit after PR #168): file sizes,
migrations, the API layer, the web app, the Expo apps, CI and workflows, plus targeted reads of the
risky spots. Nothing was run against staging or production. Where a statement is inferred rather
than read, it says "verify". Earlier reviews (`architecture-2026-10.md`, `security-2026-10.md`,
`privacy-2026-10.md`) predate roughly 25 migrations and most of the shifts, quotes, documents and
CRM work, so they are not a substitute for this one.

## Verdict

The core design is sound and unusually disciplined for this stage: tenant isolation is enforced in
Postgres, money and time follow the stated rules, providers are swappable, and CI is real. It is
**not yet ready for paying businesses**. The blockers are almost all operational (hosting plans,
scheduler, monitoring, backups, abuse limits), not architectural. Fixing them does not need a
redesign.

## What is solid (keep it, do not "improve" it)

1. **Tenant isolation in the database.** `app/core/db.py` runs every transaction as the `app_api`
   role with `app.user_id` / `app.tenant_id` set transaction-locally, re-applied after each
   commit. `tests/test_database_security.py::test_every_table_has_row_level_security` checks every
   table generically, so a new table without RLS fails CI. (A naive scan of the migrations shows
   many tables "without RLS"; that is a false alarm, because RLS is enabled in loops. The test is
   the right source of truth.)
2. 67 linear migrations, 60 tables, 54 tenant-scoped; security-definer functions are tested for a
   pinned `search_path`; `alembic_version` is locked.
3. Providers behind interfaces (`app/providers/`), disabled until chosen. Matches the paid-provider
   decision.
4. Generated, CI-checked API client (`pnpm api:generate` + `git diff --exit-code`).
5. Rate limiter with a pluggable store, security headers on both API and web, signed file links.
6. About 358 API tests, 17 TypeScript test files, about 40 Playwright/Python e2e scripts.

## Blockers before real customers (do these first)

| # | Finding | Why it matters | What to do |
|---|---|---|---|
| B1 | **Hosting plans.** Vercel Hobby (its terms limit it to non-commercial use), Render free tier (sleeps, so occasional 502), Supabase free (no leaked-password protection, no point-in-time recovery). | Real businesses cannot be served from these, and Hobby is a terms-of-service problem once money flows. | Decide the go-live stack: Vercel Pro (or move web to another host), Render Starter or above, Supabase Pro. Record it in `docs/DECISIONS.md`. Cost decision for Adir. |
| B2 | **Background jobs run as GitHub Actions cron** (`jobs-staging.yml`, `jobs-hourly-staging.yml`, keep-alive). GitHub schedules are best-effort (delays of many minutes, skipped runs under load) and are disabled after 60 days without repository activity. The hourly workflow shares the `migrate-staging` concurrency group with migrations. | Reminders, message outbox, publish-shifts, billing and document issuing all depend on it. A silent stop means missed reminders and unsent invoices with nobody noticing. | Move to a real scheduler: Render cron jobs or a worker service running `python -m app.jobs <name>`. Add a heartbeat table (`job_runs`: name, started, finished, ok) and alert if a job is overdue. Keep jobs idempotent (verify each one is; `send-messages` and `issue-documents` most of all). |
| B3 | **No error monitoring or structured logging.** Only one module under `app/` uses `logging`; no Sentry/OpenTelemetry in API or web. | The first production bug will be invisible. | Add Sentry (free tier is fine) to API, web and Expo apps; request-id middleware; JSON logs; never log request bodies (privacy review). Add an uptime check on `/health/ready`. |
| B4 | **Backups and restore are untested.** Nothing in the repo documents a restore drill. | RLS and migrations are irrelevant if the data is lost. | After B1, enable daily backups plus PITR, and write `docs/deploy/restore-runbook.md`; do one real restore into a scratch project and record the time it took. |
| B5 | **Prototype payment paths must be unreachable in production.** `POST /billing/payment-method` (`add_test_card`) and `simulate-payment` exist. `simulate_payment` is guarded by `checkout.simulated`; I did not find an equivalent guard on `add_test_card`. | A production tenant could "pay" with a fake card. | Gate both behind `settings.is_production` (config already has `environment`) or the active provider being the simulated one; add a test that production mode returns 404/403. Verify before go-live. |
| B6 | **No dependency or code scanning in CI.** `.github/` has workflows only: no Dependabot, CodeQL, `pnpm audit` or `pip-audit`. | Known-vulnerable packages ship unnoticed. | Add `dependabot.yml` (npm, pip, github-actions), CodeQL for JS and Python, and `pip-audit` / `pnpm audit --prod` as non-blocking CI steps first. |

## High priority (before or right after launch)

**H1. Unbounded list endpoints.** About 278 endpoints, but `LIMIT`/pagination appears in only a
handful of files (messaging log, receipts, a few others). Lists for clients, bookings, sessions,
leads, notifications, audit log and shifts are returned whole. Fine for demo data, a latency and
memory problem for a studio with 20k clients. Add one shared pagination dependency
(`limit` default 50 / max 200, keyset on `(created_at, id)`), apply it endpoint by endpoint
starting with clients, leads, bookings, notifications, audit; update the web tables and Expo lists
to load more.

**H2. Index review is unproven.** My scan of the migrations found 25 tenant-scoped tables where no
index mentioning `tenant_id` was visible (for example `messages`, `notifications`, `payments`,
`client_notes`, `lead_activities`, `shift_templates`). The scan is crude (it cannot see indexes
created in loops or implied by unique constraints), so **verify with real data**: seed the
networks demo at 50x size on a scratch database, run `EXPLAIN (ANALYZE, BUFFERS)` on the 15
busiest queries (dashboard, schedule list, shifts board, client list, reports, message log), add
composite indexes `(tenant_id, <filter column>, <sort column>)` where scans appear. Add a test
that lists tenant tables with no leading-`tenant_id` index so the question stays answered.

**H3. Raw SQL composed with f-strings.** The API uses SQLAlchemy `text()` throughout (a reasonable
choice for RLS-heavy code), and in places composes fragments with f-strings
(`app/api/locations.py:108,273`, `app/api/client_app.py:148-243`, `app/reports/metrics.py:284`).
The fragments I read come from constants or allow-listed keys, so I found no injection, but
`set_clause(changes)` builds SQL from dict keys. Audit each f-string `text()` call, make
`set_clause` validate keys against a per-endpoint allow-list, and add a ruff rule or CI grep that
fails on a new f-string inside `text(`.

**H4. Rate limiting is per process and in memory** (`app/core/rate_limit.py`), and the API sleeps
on the free tier, so counters reset. With one instance this is acceptable; with two it silently
halves protection. Add a Redis-backed store (the interface already exists) when scaling past one
instance, and confirm `API_TRUST_FORWARDED_FOR` is only honoured behind the known proxy.

**H5. AI cost control.** The gateway sets `max_tokens=16000` per call and the provider rate-limit
error is handled, but I found no per-tenant daily token or message cap. Usage events exist, so
the data is there. Add a per-plan daily cap enforced in `ai/gateway.py`, soft-warn at 80% like the
other quotas. This is the one place a single tenant can create unbounded cost.

**H6. Web security headers.** ✅ Report-only nonce CSP, report endpoint and HSTS done (2026-10-12); switch to enforcing once reports are clean. The web app sends only `frame-ancestors 'none'` as its CSP. Add a
real CSP (script-src with nonces for Next, `connect-src` limited to the API and Supabase), HSTS
(Vercel adds it on its domain; set it for the custom domain), and test with a report-only header
first.

**H7. Auth hardening not yet possible on free plans.** Leaked-password protection needs Supabase
Pro. The OTP flow (just fixed to accept any length) should also get: attempt limits visible to the
user, and an explicit email-OTP length setting in `supabase/config.toml` that matches hosted (the
local file says 6 while hosted sends 8; the UI is now length-agnostic, but keep the two aligned).

## Structure and maintainability (medium)

**M1. The shared mobile kit is under-used.** `packages/app-kit` has 28 files, and `src/screens`
contains only `sign-in-screen.tsx`. The three Expo apps each hold their own screens, with large
files such as `apps/business-app/src/app/session/[id].tsx` (512 lines) and `client/[id].tsx`
(507). Move shared screens (client profile, session detail, empty/error states, the LoadError
retry card pattern) into app-kit, and split screens above about 300 lines into hook + view.

**M2. Oversized web components.** `start-wizard.tsx` (731), `shift-board.tsx` (484),
`calendar-board/time-grid.tsx` (450). 90 of 219 `.tsx` files are `"use client"`; check that pages
which only render data are server components and that client islands are small. Split by
responsibility (state hook, toolbar, grid, dialogs) when next touched, with no behaviour change.

**M3. Oversized API functions.** `app/seed/business.py::seed` is 661 lines in one function;
`_seed_practice` 164; `privacy.export_client` 153; `ai/demo.py::_answer` 135; `catalog/welcome.py::build_welcome`
116; `main.py::create_app` 111. The seed split into a package was started in #122; finish by
breaking `seed()` into per-domain steps. `export_client` should iterate a registry of
"tables that hold client data" (also the basis for a test that every new client-linked table is
covered by export and erase, which is a privacy-law risk when forgotten).

**M4. API modules are large and flat.** `app/api/` has 49 endpoint files; the domain logic lives
partly in `api/*.py` (schedule.py 766 lines, resources.py 624, shifts.py 578, quotes.py 550) and
partly in domain packages. Rule going forward: endpoints parse, authorise and call; SQL and rules
live in the domain package. Move opportunistically, one file per PR, tests unchanged.

**M5. Migration safety.** The duplicate `0058` id incident (fixed in #147/#148 by making 0058/0059
re-runnable) shows the chain is easy to break with parallel branches. Add CI checks: single
Alembic head, unique revision ids, and "upgrade from the previous release's schema" (not only an
empty database). Document the rule for parallel threads: reserve migration numbers in the PR
description.

**M6. E2E tests are not visibly part of CI.** `ci.yml` runs `turbo run lint typecheck test build`;
the `e2e/` scripts are run by hand (verify there is no separate workflow). Add a nightly workflow
(not per-PR) that runs the e2e suite against a Supabase started from the mirror image, and fails
loudly. Keep the per-PR job fast.

**M7. Documentation drift.** `docs/STATUS.md` and the Hebrew twin are updated per PR, but the
three 2026-10 reviews are now stale; supersede them with this one and a short "status of each
earlier follow-up". `docs/spec/archive/v3` should get a "what is built vs. planned" column.

## Product-readiness checks (before the first real business)

1. Legal: privacy policy, terms of service, cookie banner, data-processing agreement, in Hebrew and
   English. Israeli Privacy Protection Law amendment 13 and, for EU, GDPR: the export/erase work in
   `privacy.py` and the retention job cover the mechanics; the documents still need a lawyer.
2. Account closure and departed-business deletion (deferred in #129) must exist before launch, or
   the 90-day retention promise cannot be kept.
3. Real email provider (Resend free tier is enough to start) so sign-in, invitations and receipts
   leave the sandbox. Payments (#46) and invoicing (#47) stay disabled until the business
   operates, as decided.
4. Support path: a real support address, status page, and a documented on-call routine.
5. Native distribution: the Expo apps are published as web apps; the store builds (EAS, app
   identifiers, icons, store listings, privacy labels) are not set up (verify).
6. Accessibility pass on the main journeys with a real screen reader and RTL on a real phone; the
   code follows the rules, but nobody has audited the finished screens.
7. A load test on the three busiest journeys (open schedule, book, shifts board) at 10x the demo.

## Suggested execution order (each item is one short thread / PR)

1. B5 (production guard on prototype payments) and B6 (Dependabot, CodeQL, audit): small, no cost.
2. B3 (Sentry, request ids, structured logs, uptime check).
3. B2 (scheduler move + job heartbeat + alert); needs B1 decided.
4. H2 (indexes with real data) then H1 (pagination), together, on the largest lists first.
5. H3 (f-string SQL audit), H5 (AI cap), H6 (CSP).
6. B1 and B4 once Adir approves costs; then the restore drill.
7. M5, M6, then M1-M4 as background cleanup between features. Do not refactor and add features in
   the same PR.

Model guidance: Sonnet for 1, 2, 4 (pagination), 7; Opus for B2 design, H2 index design, and any
schema change; keep each thread to one numbered item.

## What I could not verify

Live staging behaviour (query plans, job reliability, real latency), every endpoint's permission
dependency (the scan was not reliable, so rely on the tenant-isolation and permission tests plus a
new test that walks the OpenAPI schema and asserts every non-public route returns 401 without a
token), and the Expo native build state. Items marked "verify" above should be confirmed first.
