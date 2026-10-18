# Go-live scorecard (rehearsal, October 2026)

Slice GL24, the last go-live slice. Every topic of the go-live plan (section 1 and 2 of
`docs/proposals/go-live-readiness-2026-10.he.md`) with its state today.

- ✅ built and checked, nothing left in code
- 🟡 built; the last step is the owner's, or needs a paid plan or an account (named in the last column)
- 🔴 not built

**Result: no 🔴 left. Every row below is ✅ or 🟡. All 🟡 are the owner's step (account, payment, lawyer) except one code item, named in the table: a limited database role for background jobs.**
The remaining work sits in [go-live-day.md](../deploy/go-live-day.md) and
[go-live-checklist.md](../deploy/go-live-checklist.md).

How it was checked: the CI job (lint, types, about 650 API tests including tenant matrix, production
guards, key rotation, k6 load run), the nightly end-to-end run with blocking accessibility checks,
the [OWASP ASVS level 1 self-check](go-live-asvs-self-check-2026-10.md), and the CI rehearsal
(`.github/workflows/rehearsal.yml`, results at the end of this file). Nothing was deployed and
nothing in production was touched.

## 1. The 15 topics

| # | Topic | State | Pull request | What is left, and who |
|---|---|---|---|---|
| 1 | HTTPS and HSTS | ✅ | #385 | `includeSubDomains` with the real domain (checklist, GL5) |
| 1 | WAF / DDoS | 🟡 | #396 | Cloudflare in front of the domain (free) or Vercel Firewall (Pro): owner, at domain set-up; steps in [go-live-checklist.md](../deploy/go-live-checklist.md) "Firewall in front of the website and API (WAF)", plus A8 (company, bank, insurance) and A12 (penetration test) |
| 1 | Rate limiting | ✅ | #405 | Shared limiter store needs Render Key Value before a second API instance (documented in `production.md`) |
| 1 | SQL injection | ✅ | #384 | Automatic test on every new f-string in SQL; ruff `S` |
| 1 | XSS and CSP | ✅ | #385 | Nonce policy enforced |
| 1 | Security headers | ✅ | this PR | API answers now also default to `Cache-Control: no-store` |
| 1 | File uploads | 🟡 | #388 | Type by bytes and size done; virus scanning built, off (about $7 a month) |
| 2 | Two-step sign-in | 🟡 | #386 | Owner turns it on for their own accounts; staging already requires it |
| 2 | Password policy | 🟡 | #386 | 10 characters, letters and digits applied; leaked-password check needs Supabase Pro |
| 2 | Roles and permissions | ✅ | - | Existing, with matrix tests |
| 2 | Sessions | ✅ | #386 | Idle sign-out; "Sign out of all devices" is on the web (Account, Account security); the app has no button yet (ASVS 3.6) |
| 2 | Break-in attempts | ✅ | #392 | Audit log of sign-ins and sensitive actions |
| 3 | Row security on every table | ✅ | - | `test_tenant_matrix.py`, `test_database_security.py` |
| 3 | Branch separation | ✅ | #387 | Client notes, documents, health, dependents, receipts, quotes |
| 4 | Encryption at rest and in transit | ✅ | - | Provider disk and TLS, plus field encryption |
| 4 | Key rotation | ✅ | #389 | `rotate-secrets` job and procedure |
| 4 | Secrets management | ✅ | #384 | gitleaks in CI and nightly |
| 4 | Least privilege | 🟢 | - | The API runs as a limited role without row security bypass. Background jobs switch to `app_jobs` (migration 0128): all businesses, rows only, no schema changes, no TRUNCATE, no triggers. `API_JOBS_DB_ROLE=` (empty) turns it off |
| 4 | Access to production | 🟡 | #396, #407 | Two-step sign-in on Supabase, Render, Vercel, GitHub: owner |
| 5 | Production server | 🟡 | #396 | Written as code, off. Render Starter and Supabase Pro at go-live: owner approves |
| 5 | Indexes | ✅ | #403 | Trigram index for client search; index tests |
| 5 | Connection pooling | ✅ | #405 | Worst case 60 connections worked out in `production.md` section 1; compare with the Supabase compute limit at go-live |
| 5 | Load tests | ✅ | #405 | k6 parallel run in CI (50 to 200 users) |
| 5 | Paging of lists | ✅ | #403 | Keyset paging; the CRM quotes list got "load more" in #431. Open: the Expo lists still page by offset (see GL17 in the coverage audit) |
| 5 | Autoscaling | 🟡 | #405 | Second instance after the Key Value limiter store (paid, later) |
| 6 | Health checks | ✅ | #396 | `/health` live, `/health/ready` database; the host checks readiness |
| 6 | Migrations on release | ✅ | #396 | One pre-deploy step in production |
| 6 | Recovery plan | ✅ | #397 | Restore runbook, drill rehearsed in CI (below); real drill after A2 |
| 6 | Redundancy | 🟡 | #396 | Two API instances and PITR are paid, later |
| 7 | Database backup | 🟡 | - | Supabase Pro daily backup: owner pays at go-live |
| 7 | Second backup | 🟡 | #397 | Built, off until the Cloudflare R2 account (task A2) |
| 7 | File backup | 🟡 | #397 | Same |
| 7 | Restore test | 🟡 | #397, this PR | Rehearsed on a throwaway database in CI; the first drill from R2 is the owner's after A2 |
| 8 | Logs | ✅ | - | JSON with request id |
| 8 | Error tracking | 🟡 | #400 | Sentry account and three DSNs: owner (free) |
| 8 | System health page | ✅ | #400 | Console "System health" |
| 8 | Response times | ✅ | #400 | p95 per route |
| 8 | Outage alerts | 🟡 | #400 | UptimeRobot with phone alert and the test-alert workflow: owner (free) |
| 8 | Status page | 🟡 | #400 | Free status page and `NEXT_PUBLIC_STATUS_URL`: owner |
| 9 | Vulnerable libraries | ✅ | #384 | pip-audit, pnpm audit, Dependabot |
| 9 | Secrets in code | ✅ | #384 | gitleaks |
| 9 | Image scan | ✅ | #384 | Trivy |
| 9 | Code analysis | ✅ | #384 | ruff `S`, ESLint rules (CodeQL is paid for private repositories) |
| 9 | API tests | ✅ | - | About 650 tests |
| 9 | Penetration test | 🟡 | this PR | Self-check done (84 lines, no 🔴). A professional test after 20 to 50 businesses: owner, paid |
| 10 | Separate environments | 🟡 | #396 | Production defined as code; created at go-live |
| 10 | CI | ✅ | #399 | Required checks plus nightly end-to-end |
| 10 | Deploy | ✅ | #399 | Production only from a version tag with approval; staging from main |
| 10 | Rollback | ✅ | #399 | Rollback workflow, expand-then-contract migrations; rehearsed in CI (below) |
| 11 | AI tool permissions, quotas, approvals | ✅ | - | Existing |
| 11 | Prompt injection | ✅ | #388 | Untrusted content wrapped as data |
| 12 | Privacy policy and terms | 🟡 | #394 | Drafts with version records; lawyer and real company details: owner |
| 12 | Data processing agreement | ✅ | #394 | DPA and sub-processors pages |
| 12 | Consent records | ✅ | #394 | Version and time stored; re-accept banner |
| 12 | Data deletion and export | ✅ | #390 | Business export, account deletion, invoices kept |
| 12 | Marketing opt-in and opt-out | ✅ | #391 | Toggle, opt-out link, "advertisement" marking |
| 12 | Amendment 13 papers | 🟡 | #407 | Drafts in `docs/legal/`; lawyer and security officer appointment: owner |
| 12 | Accessibility | 🟡 | #395 | Blocking axe checks; the accessibility coordinator's name, phone and email: owner |
| 12 | Cookies | ✅ | - | Necessary cookies only |
| 13 | Payments provider | 🟡 | - | Adapter built, off by decision; real provider (#46) when the business operates |
| 13 | Simulated payment in production | ✅ | #388 | Returns 404 in production |
| 13 | Invoices with VAT and numbering | ✅ | #408 | VAT 18 percent, running numbers |
| 13 | Collection and debts | ✅ | #408 | Reminders, grace period, read-only, then pause |
| 13 | Cancelling and changing plan | ✅ | #408 | Without closing the business |
| 14 | Audit log | ✅ | #392 | Screen for owners and managers |
| 14 | Support requests | 🟡 | - | Inbox built; a real support address: owner |
| 14 | Incident procedure and templates | ✅ | #407 | `incident-templates.md`, `on-call.md` |
| 14 | Telling customers | ✅ | #407 | Incident banner in console, web and app |
| 15 | AI limits | ✅ | - | Credit caps 400 and 1200 |
| 15 | Message limits | ✅ | #406 | 80 and 100 percent alerts; fair send queue |
| 15 | Storage limits | ✅ | #388, #406 | Checked on every upload type |
| 15 | API limit per business | ✅ | #405 | Per-business request ceiling |

## 2. Extra topics

| # | Topic | State | Pull request | What is left, and who |
|---|---|---|---|---|
| 16 | Background jobs at scale | ✅ | #398 | Batches, run locks, tests |
| 17 | Emails that reach the inbox | 🟡 | #409 | Sending domain, Resend account, DNS records (task A6) |
| 18 | Store readiness | 🟡 | #404 | Store accounts and final app identifier (task A: Apple $99 a year, Google $25 once) |
| 19 | Staging not indexed | ✅ | #385 | Verified by test |
| 20 | Code order and file sizes | ✅ | #410, #414, #415, #416, #417 | The last GL25 pull request is the only open cleanup and changes no behaviour |
| 21 | Stale documents | ✅ | #410 | Corrected |
| 22 | One key forever | ✅ | #389 | Rotation built |
| 23 | Export the whole business | ✅ | #390 | Built |
| 24 | Go-live rehearsal | ✅ | this PR | This file, the ASVS check, the CI rehearsal, the runbook |
| 25 | Product metrics | ✅ | #406 | Product events inside our own database; no third party |
| 26 | Company details and contracts | 🟡 | - | Real company, bank account, liability and cyber insurance: owner |

## 3. Rehearsal results (CI, throwaway Postgres 17)

Workflow: `.github/workflows/rehearsal.yml` (manual, and on every change to the workflow itself).

Run of 2026-10-17 on commit `229cedc` (all steps green):

| Step | Result |
|---|---|
| Migrations from empty to head `0124` | 3 s |
| Newest migration (0124) down and up again | ok, head unchanged |
| Encrypted dump (`pg_dump` into `age`) | under 1 s |
| Restore (decrypt, restore, smoke checks) | 2 s; row counts equal in 129 tables (11 rows); 164 row security policies in both |
| Database stopped: `/health` | 200 (the process is alive) |
| Database stopped: `/health/ready` | 503 (what the uptime monitor alerts on) |
| Recovery after the database came back | 10 s until `/health/ready` was 200 again |

Limits of this run: the database holds only what the migrations create (11 rows), so the dump and
restore times say that the chain works, not how long a real database takes. The first real drill
(after task A2) measures that and goes into the table in `restore-runbook.md`. The outage ran on
one API process, not the two workers of production.

What was not rehearsed, and why:

- A real restore from Cloudflare R2 and the alert reaching the owner's phone: both need accounts that
  do not exist yet (tasks A2, GL13 manual check). They are steps 4 and 6 of the go-live day.
- A production deploy and rollback of the website and the API on real hosts: forbidden until the
  owner approves one deploy after all work is finished. The rollback workflow and the pre-deploy
  migration step are exercised by their tests and the CI step-back above.
- The 24 hour load profile: the k6 parallel run in CI is the standing check; a sustained run on the
  paid production service is step 7 of the go-live day.
