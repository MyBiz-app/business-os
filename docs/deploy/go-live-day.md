# Go-live day (runbook)

The order in which everything that is built and switched off gets switched on, who does each step,
and how to go back. Written in the GL24 rehearsal. Nothing here has been done: no production
service exists yet. Each step links to the document that has the detailed instructions.

Rules for the day:

- One person changes one thing at a time; the next step starts only when the check of the previous
  one passes.
- Do not deploy the website until the owner has said so in writing; the deploy is one run of the
  "Deploy the web (production)" workflow from a version tag.
- Costs start with step 2. The owner approves each paid plan first (decision of 2026-10-12).
- If a check fails, stop and use "Going back" at the end.

Who: **Owner** is Adir. **Claude** is a Claude Code session working in the repository and the
connected tools (GitHub, Render, Supabase, Vercel); it can do any step marked Claude once the owner
has approved the cost.

## Before the day (free, can be done any time)

| Step | Who | Detail |
|---|---|---|
| Two-step sign-in on the owner's own Supabase, Render, Vercel, GitHub and MyBiz accounts | Owner | [on-call.md](on-call.md), [auth-settings.md](auth-settings.md) |
| Sentry account, three DSNs; UptimeRobot with phone alert; free status page | Owner | [monitoring.md](../guides/monitoring.md) |
| Cloudflare R2 bucket, token, `age` key; set `OFFSITE_BACKUP_ENABLED=true`; run the first restore drill and fill the table | Owner | [restore-runbook.md](restore-runbook.md), task A2 |
| Domain and sending domain (Resend); SPF, DKIM, DMARC; mail-tester 10 of 10 | Owner | [email-domain.md](email-domain.md), task A6 |
| Lawyer reviews `docs/legal/`, terms, privacy and DPA; real company details in `brand.json` | Owner | [legal README](../legal/README.md) |
| Accessibility coordinator name, phone and email in the statement | Owner | [accessibility-checklist.md](../guides/accessibility-checklist.md) |
| App store accounts and the final app identifier | Owner | [go-live-checklist.md](go-live-checklist.md) "App stores" |
| Firewall (WAF) in front of the site and API; company, bank account and insurance (A8); penetration test (A12) | Owner | [go-live-checklist.md](go-live-checklist.md) sections "Firewall in front of the website and API (WAF)", "Company, bank account and insurance (A8)", "Professional penetration test (A12)" |
| Run the CI rehearsal once more on the commit that will be released | Claude | Actions: "Go-live rehearsal (CI)"; all steps green |

## The day, in order

| # | Step | Who | Cost | Check before moving on |
|---|---|---|---|---|
| 1 | Freeze: no merges to `main` except the release; confirm CI and the nightly end-to-end are green on the release commit; tag `vX.Y.Z` | Claude | free | Release notes written by `release.yml` |
| 2 | Supabase Pro project for production, then the auth settings workflow with the leaked-password check | Owner approves, Claude applies | about $25 a month | [production.md](production.md) step 1; the advisors show no new warnings |
| 3 | Render: apply `render.production.yaml` (API Starter, health check on `/health/ready`, pre-deploy migration, the two job crons). Stop the staging job schedules that point at the same database | Claude | about $7 a month for the API plus crons | `GET /health/ready` is 200; the migration ran once; `job_runs` has a first row |
| 4 | Production settings: the first six variables (the API refuses to start without them), key list, internal token, CORS, storage | Owner pastes the secrets | free | The API starts; `tests/test_production_guards.py` list matches the variables |
| 5 | Backups: daily Supabase backup is on; run the R2 backup once by hand and then the restore drill | Owner | free | The drill table in [restore-runbook.md](restore-runbook.md) has a real time under 2 hours |
| 6 | Monitoring: send a test alert (workflow "Send a test alert"), then stop the API for two minutes and see the phone alert and the status page | Owner | free | The phone alert arrives in under 5 minutes |
| 7 | Load: run the k6 parallel profile against the production URL once with the demo tenant, then remove the demo data | Claude | free | p95 under 2 seconds at 100 users |
| 8 | Website: with the owner's written approval, run "Deploy the web (production)" from the tag; set `WEB_ALLOW_INDEXING`, `WEB_HSTS_INCLUDE_SUBDOMAINS` and the status address | Owner approves, Claude runs | Vercel Pro about $20 a month | Pages load; headers show the nonce CSP and HSTS; the workflow's own health check passes |
| 9 | Email: switch the sending provider on and send a real sign-in code and a quote email | Owner | free to 3,000 a month | Both arrive in the inbox, not spam |
| 10 | Create the first real business; sign up through the public journey with a fresh account | Owner | free | Terms acceptance is stored; welcome email arrives; two-step sign-in enforced for the owner |
| 11 | Payments, invoicing, virus scanning, WhatsApp and SMS stay **off** until the business operates (decision 2026-10-12). Each has its own "switch on" section in [go-live-checklist.md](go-live-checklist.md) | Owner decides later | paid | Not part of the day |
| 12 | Tell the team: status page link, support address, on-call roster, incident templates | Owner | free | [on-call.md](on-call.md) updated with real phone numbers |

## Going back

| Problem | What to do |
|---|---|
| The new API version fails its health check after a deploy | The deploy workflow rolls back by itself. By hand: Actions → "Roll back", environment `production`, component `api` |
| The website misbehaves | Actions → "Roll back", component `web`. The previous production deployment is promoted again |
| A migration broke something | Do not downgrade in production. Migrations only add first, so the previous API version still runs on the newer database: roll back the API, then fix forward ([releases.md](releases.md)) |
| The database is damaged or data was lost | [restore-runbook.md](restore-runbook.md): Supabase backup or point in time restore, or the R2 dump into a scratch project; target is 2 hours to be back |
| An alert fires and nobody knows why | [on-call.md](on-call.md), then post the matching text from [incident-templates.md](incident-templates.md) and open the incident banner in the console |
| A paid service was switched on by mistake | Turn the plan down in the provider's dashboard; no code change is needed because every paid adapter is behind its own switch |
| The whole launch must stop | Put the console in maintenance with a platform broadcast, point the domain back to the holding page, and keep staging running |

## What the CI rehearsal already proved

See "Rehearsal results" in [the scorecard](../reviews/current/go-live-scorecard-2026-10.md): from-empty
migration time, one migration down and up, an encrypted dump restored with equal row counts and
policies, and the readiness probe going from 200 to 503 and back during a database outage. Steps 5
and 6 above repeat the last two on the real services.
