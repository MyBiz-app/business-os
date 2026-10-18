# Go-live checklist

Copy of section 1 of the 2026-10-11 remaining-work plan, plus how each item is switched on in
code. Everything marked **off** is built and disabled; nothing that costs money turns on by itself.
Tick items here as they are done (and record cost decisions in `docs/DECISIONS.md`).

The order of the day itself, with who does what and how to go back, is in [go-live-day.md](go-live-day.md); the state of every topic is in the [scorecard](../reviews/go-live-scorecard-2026-10.md).

## Blockers

| # | Item | State | To switch on |
|---|---|---|---|
| P0-1 | Production environment: Vercel Pro, Render Starter or above, Supabase Pro, backups. About $55-75 a month | Owner approves first | Create the services, then set the variables below |
| P0-2 | Background jobs as Render cron (GitHub schedules skip runs) | Built, **off** | Stop the staging GitHub schedules for the same database, then Render → New → Blueprint → `render.production.yaml`. Set `API_DATABASE_URL` and `API_SECRETS_KEY` when asked. The two crons run `run-daily` and `run-hourly`, which already include the payroll jobs (`remind-payroll` daily, `notify-payslips` hourly), so no extra scheduler is needed; the GitHub workflows `jobs-staging.yml` and `jobs-hourly-staging.yml` are staging only |
| P0-3 | Monitoring: JSON logs and request ids exist; error tracking (Sentry) and an uptime monitor do not | Built (GL13), **off** until accounts exist | Follow [monitoring.md](../monitoring.md): Sentry DSNs, UptimeRobot on `/health/ready` with phone alert, status page and `NEXT_PUBLIC_STATUS_URL` |
| GL13 | Alerts to the owner's phone for a failed or late job; console "System health" page | Built | **Your manual check:** sign in to the MyBiz app on your phone once, then run the GitHub workflow "Send a test alert (staging)"; the push and email must arrive. Then the real test: in staging, stop one job's workflow for a day and see the `check-jobs` alert |
| P0-7 | Files in object storage | Built | `API_STORAGE_PROVIDER=supabase` and `API_STORAGE_SETTINGS` (see `docs/STATUS.md`) |
| P0-8 | Supabase Auth settings applied from CI | Built | Add `SUPABASE_ACCESS_TOKEN` to the GitHub environment; see `auth-settings.md` |
| P0-9 | Legal text from a lawyer (privacy policy, terms, DPA, cookie banner); account closure and 90-day deletion | Closure built; text open | Lawyer; real deletion is enabled with `--apply` on `delete-closed-businesses` |
| B4 | Backups and a restore drill | After P0-1 | Follow `restore-runbook.md` and fill in its drill table |
| GL22 | Emails that reach the inbox: SPF, DKIM, DMARC on the sending domain; bounces and spam complaints stop further sends | Built, **off** until a domain and a Resend account exist (free up to 3,000 emails a month, domain about $15 a year) | Owner task A6: follow [email-domain.md](email-domain.md) (DNS records, API variables, Resend webhook, Supabase SMTP), then check 10/10 on mail-tester |
| GL15 | Second backup (encrypted database dump + files to Cloudflare R2, 30 days) and quarterly restore drill | Built, **off** (free) | Owner task A2: follow "Switching it on" in `restore-runbook.md` (Cloudflare account, bucket, token, age key, GitHub secrets, then variable `OFFSITE_BACKUP_ENABLED=true`) and run the drill |
| GL23 | Incident banners (console, web, app) and the Amendment 13 papers in `docs/legal/` | Built | Owner tasks in "Incident response and Amendment 13 (GL23)" below |
| B5 | Test cards refused in production | Done (#191) | Nothing |
| GL3-a | `simulate-payment` returns 404 in production; uploads are checked by their bytes and by the storage allowance (logo, cover, branch logo, AI agent picture, documents, files area, migration files) | Done | Nothing |
| GL3-b | Virus scanning of uploads (ClamAV) | Built, **off** (costs about $7 a month for the scanner service) | See "Switching on virus scanning" below |

## Production as code (GL12)

The whole production set-up is written down and **off**: [production.md](production.md) is the step
by step (Supabase project, Render Blueprint, Vercel project, GitHub `production` environment,
variables, releases, who can reach what). Files: [`render.production.yaml`](../../render.production.yaml)
(API web service + the two job crons), [`deploy-web-production.yml`](../../.github/workflows/deploy-web-production.yml)
(from a `v*` tag, with approval), the `production` build profile in `apps/client-app/eas.json`.

| Paid item | State | Cost (monthly, list price) | To switch on |
|---|---|---|---|
| Render API (Starter, no sleep, pre-deploy migration, readiness check) | Built, **off** | about $7 | production.md section 2 |
| Render job crons (daily, hourly) | Built, **off** | about $14 for the two | production.md section 2 |
| Supabase Pro (separate production project, backups, leaked-password check) | Built, **off** | about $25 | production.md section 1 |
| Vercel Pro (production site, domain, more deployments) | Built, **off** | about $20 per seat | production.md section 3 |
| Apple Developer program (iOS) | Not bought | about $99 a year | production.md section 7 |

## Production settings (the API will not start without the first six)

| Variable | Value |
|---|---|
| `API_ENVIRONMENT` | `production` |
| `API_DATABASE_URL` | Supabase session pooler string, with the password |
| `API_JWKS_URL` | `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json` |
| `API_SECRETS_KEY` | A Fernet key (encrypts businesses' provider secrets); keep a copy in the secret store; to rotate it, see [runbooks/key-rotation.md](../runbooks/key-rotation.md) (`API_SECRETS_KEYS`) |
| `API_INTERNAL_TOKEN` | A long random value, the same on Render and Vercel |
| `API_WEB_URL`, `API_API_URL` | The public addresses (not localhost) |
| `API_CORS_ORIGINS` | JSON list of the real web and app origins (not localhost) |
| `API_TRUST_FORWARDED_FOR` | `true` behind Render's proxy |
| `API_MFA_REQUIRED_FROM` | A date (`YYYY-MM-DD`) 14 days after go-live: from then owners and managers need an authenticator code for sensitive actions (settings, pay, ID numbers, team roles, closing the business). The MyBiz team always needs one. Without it, required from the start |
| `API_MFA_ENFORCED` | Leave unset (on everywhere but local development) |
| `API_RATE_LIMIT_REDIS_URL` | Optional; only when running more than one API instance: a Render Key Value, internal URL (**off**, steps in [staging.md](staging.md)) |
| `API_TENANT_RATE_LIMIT_PER_MINUTE` | Optional; the most signed-in requests one business may make a minute, default 600 (GL18) |
| `API_ANTHROPIC_API_KEY`, `API_EMAIL_*` | Optional until the AI assistant and real email are wanted |

## Website headers (slice GL5)

Set on the Vercel project that serves the website. The defaults are the safe ones for staging.

| Variable | Value | When |
|---|---|---|
| `WEB_ALLOW_INDEXING` | `true` | **Production only.** Without it every page sends `noindex` and `robots.txt` blocks all crawlers. Leave it unset on staging and previews |
| `WEB_HSTS_INCLUDE_SUBDOMAINS` | `true` | Only after the real domain is live and **every** subdomain (app, api, mail, any test site) serves valid HTTPS. It cannot be undone from the server: browsers remember it for two years |
| `WEB_CSP_MODE` | `report-only` | Emergency switch only: if a page is found broken by the Content-Security-Policy, set this to stop enforcing it while the cause is fixed (violations still go to `/api/csp-report`). Remove it afterwards |

Steps at go-live: set `WEB_ALLOW_INDEXING=true` on the production project, redeploy, and check
`https://<domain>/robots.txt` and that a page has no `X-Robots-Tag` header; after the domain and its
subdomains work, set `WEB_HSTS_INCLUDE_SUBDOMAINS=true` and check the `Strict-Transport-Security`
header; submit the sitemap to Google Search Console. A new outside service the browser must reach
directly (not through the Next.js server) needs its origin added to `apps/web/src/lib/csp.ts`.

## Switch-on steps that need a paid plan (GL1)

| Item | State | To switch on |
|---|---|---|
| Leaked-password check (Supabase) | Built, **off** (needs the Pro plan) | Upgrade the Supabase project, then run the workflow "Apply Supabase auth settings" with "apply" and "paid_plan" ticked. Checks the password against known leaks on sign-up and password change |
| Server-side session timeouts (Supabase `[auth.sessions]`) | Not used | The web app signs out after 12 hours idle and the app after 30 days by itself. A server-side limit is a Pro setting if wanted later |

Two-step sign-in is free and on: turn it on for your own account first (Account → Account security),
and for every provider account (GitHub, Supabase, Render, Vercel, Google, Apple).

## Releases and rollback (GL16)

Built and free (no paid item). Guide: [releases.md](releases.md). To use it in production add, in the
GitHub environment `production`: secret `RENDER_API_KEY` (optional, lets rollback and the post-deploy
check roll the API back), variables `RENDER_SERVICE_ID`, `HEALTH_API_URL`, `HEALTH_WEB_URL`, and the
repository variables `PRODUCTION_WEB_URL`, `PRODUCTION_API_URL`. Same names in the `staging`
environment to use **Roll back** there. After the single final deploy to staging, practise one
rollback and fill the table in releases.md.

## Subscription billing: VAT and collection (GL20)

Built and running on the simulated card; no real charge exists anywhere. The payment provider (#46)
stays an off adapter. What waits for you, when the business really operates:

| # | Step | Cost | Click by click |
|---|---|---|---|
| 1 | Check the VAT rate and your company details with your accountant | Free | The rate lives in the table `app.vat_rates` (18% for ILS from 2025-01-01). If it changes, tell Claude: a new row with the new `valid_from` date is added, old invoices keep their rate. The company name, number and VAT number printed on invoices come from `packages/i18n/brand.json` (`legal`), currently the fictitious ones |
| 2 | Decide the collection days | Free | Console → Billing → "Collection steps": reminder days (default 0, 3, 7), read-only (14), suspension (30). The switch turns the whole sequence off |
| 3 | Switch the daily job on in production | Free | The `dunning` job runs after `bill-businesses` in the daily jobs. In the production jobs setup add `uv run python -m app.jobs dunning` right after `bill-businesses`; check-jobs reports it as late if it stops |
| 4 | Real card payments | Provider fees | Needs the payment provider (#46): create the account, then ask Claude to turn on the adapter. Until then paying a late invoice only works with the test card |
| 5 | Allocation numbers for MyBiz's own invoices | Free | Israel's tax authority may require an allocation number on invoices above a threshold; ask your accountant, and if needed connect the invoicing provider (#47) |

## App stores (GL19)

Built and ready: app config, build profiles, listing texts (Hebrew and English), privacy and Data
safety answers, permission texts, reviewer notes, screenshot list. All in [`docs/store/`](../store/README.md).
Nothing was built for the stores, submitted or paid for. What waits for you, in order:

| # | Step | Cost | Click by click |
|---|---|---|---|
| 1 | Pick the final brand name and app id | Free | Decide the name (#36) and the id (default `app.mybiz.client`, or by the final domain). Tell Claude: it changes `packages/brand/app-ids.json` and `packages/i18n/brand.json`. **Permanent after the first upload** |
| 2 | Google Play Console account | About $25, once | [play.google.com/console/signup](https://play.google.com/console/signup), personal or organisation account, identity check (a few days). Then Create app → name, language Hebrew, App, Free |
| 3 | Apple Developer account (only if you want iOS) | About $99 a year | [developer.apple.com/programs/enroll](https://developer.apple.com/programs/enroll/), sign in with your Apple ID, enrol as an individual or organisation (approval 1 to 2 days). Then App Store Connect → My Apps → New App with the same id |
| 4 | Link the project to Expo | Free | `npx eas-cli login`, then in `apps/client-app`: `npx eas-cli whoami`. The project id is already in `app.json` |
| 5 | Production values in EAS | Free | expo.dev → the project → Environment variables → environment **production**: `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_KEY` (the production ones, see [production.md](production.md) section 7) |
| 6 | First Android build | Free tier, may queue | In `apps/client-app`: `npx eas-cli build --profile production --platform android`. Result: an `.aab` file. Install-test with the `preview` profile first |
| 7 | First iOS build | Needs step 3 | `npx eas-cli build --profile production --platform ios`; EAS asks to create the signing certificates, answer yes |
| 8 | Crash reports with readable stack traces | Free Sentry plan | With the Sentry account ([monitoring.md](../monitoring.md)): create an auth token and add `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT` as EAS secrets (app) and as Vercel variables (website). The plugin is already wired and switches on by itself when the token exists |
| 9 | Fill the store forms | Free | Paste from [listing.md](../store/listing.md); Play → Policy → Data safety and Apple → App Privacy from [data-safety.md](../store/data-safety.md); reviewer notes and test login from [review-notes.md](../store/review-notes.md); privacy URL = `<domain>/legal/privacy` |
| 10 | Screenshots and Play feature graphic | Free | [screenshots.md](../store/screenshots.md) |
| 11 | Submit to the internal track first | Free | Play → Testing → Internal testing → upload the `.aab`, add your email as a tester. iOS: `npx eas-cli submit --profile production --platform ios` then TestFlight. Only then production review |

Rules to remember: a lawyer should read the privacy policy before the first review (GL10). If a
Google or Facebook button is ever added to the app, Sign in with Apple must come in the same
release (Apple rule 4.8). Apple and Google review in 1 to 7 days and may ask questions; answers go in
the store consoles.

## Switching on virus scanning

Uploads are already checked by type (the file's own bytes) and size. Scanning for viruses needs a
ClamAV daemon (`clamd`), which is a separate service:

1. Render → New → Private Service → Docker image `clamav/clamav:stable` (about $7 a month; it needs
   at least 2 GB of memory for the signature database). Note its internal host name; clamd listens
   on port 3310.
2. On the API service set `API_FILE_SCAN_PROVIDER=clamav`, `API_FILE_SCAN_HOST=<that host>` and
   (only if different) `API_FILE_SCAN_PORT=3310`. Redeploy the API.
3. Upload the EICAR test string as a `.txt` file in the files area: it must be refused with
   `file_infected`.

While it is on, an unreachable scanner refuses uploads (`scan_unavailable`) instead of letting them
through. Switch it off again with `API_FILE_SCAN_PROVIDER=none`.

## Ads and the opt-out link (GL9)

The short opt-out link in SMS and WhatsApp ads is `API_API_URL` + `/u/<token>`, so it follows the
API's public address. When the real domain is set, change `API_API_URL` first: links already sent
keep working only on the old address. Have the lawyer read the "פרסומת" mark and the opt-out
wording (`broadcast.*` in `packages/i18n/messages`) with the other legal texts.
## Switching on sign-in removal (account deletion)

"Delete my account" in the apps empties the person's profile and disconnects them. To also delete
their login at Supabase Auth, set `API_SUPABASE_URL` (the project URL) and
`API_SUPABASE_SERVICE_KEY` (the service role key, from Supabase, Settings, API) as secrets on
the API host. Never put the key in the repository or in the apps. Without them the account can
no longer be used (the API answers `account_deleted`), but the login row stays at Supabase.

## Load test on staging (GL18)

Optional, free, at night: the real figure for "how many businesses one Starter instance holds" (the table in [the load test](../reviews/load-test-2026-10.md) is an estimate until then). Steps are in that document ("Run it", against staging); use `VUS=20`, then `50`, and write the numbers into its table. Switch the rate limits back on afterwards. When a second API instance is added, also create the Render Key Value and set `API_RATE_LIMIT_REDIS_URL` ([staging.md](staging.md)).

## Incident response and Amendment 13 (GL23)

The banner is built and free; the rest is decisions only you can make.

1. **Open a banner to try it** (2 min): Console, **Incident banners**, type "Planned maintenance", a test title, then **Resolve**. The bar shows on every page of the site and in the app while it is open.
2. **Support address and status page.** Create `support@<domain>` with the domain, and a free hosted status page; put the status address in the banner form when you open one, and fill both in `on-call.md` (Contacts) and `support.md`.
3. **Appoint the data security officer** (yourself until the lawyer says otherwise): sign the appointment text in `docs/legal/security-officer.md` and fill the name, phone and email in `docs/legal/security-procedure.he.md` section 2.
4. **A backup on-call person** with two-step sign-in on Render, Vercel, Supabase and GitHub, who has read `on-call.md`. Fill the Contacts table.
5. **Book a lawyer for one session** with `docs/legal/README.md` ("What the lawyer is asked to decide" lists the seven questions). Then replace every `{placeholder}` and the fictitious company details (`packages/i18n/brand.json`).
6. **Diary dates:** quarterly restore drill and report, yearly procedure review, vendor review and team training (the tables at the end of the legal files are the log).

## Switching on a live AI provider (and the live simulation, R19)

Built and **off**; nothing here runs or costs money until the owner says "connect". Anthropic stays
the default (`API_ANTHROPIC_API_KEY` on Render, caps 400/1200 credits unchanged). OpenAI and
Gemini have tested adapters (`app/ai/vendors.py`) that stay unreachable until all three are set:

1. The vendor's key: `API_OPENAI_API_KEY` or `API_GEMINI_API_KEY` (the owner pastes it, never in chat).
2. The vendor is named in `API_AI_ENABLED_VENDORS` (for example `openai`). Until then the
   console model picker shows it as disabled and `get_provider()` falls back to demo.
3. `API_AI_PROVIDER=openai` (or `gemini`) to make it the platform's assistant. Tiers map to the
   first registry model of that tier (`app/ai/models.py`); check the placeholder prices there
   against the vendor's price list first (an unknown model is priced as the dearest).

A business can also connect its own key (settings, Integrations, AI). Another vendor is one adapter
in `vendors.py`, one row per model in `MODELS`, and one `@register("ai", ...)` entry in
`app/providers/ai.py`. Switching back is removing `API_AI_PROVIDER`.

**Live simulation (R19).** Only after the owner confirms the API account has a balance of $5-10:
`AI_LIVE_SIM_APPROVED=yes uv run python -m app.ai.live_sim --approved --max-usd 2 --out report.md`
in `apps/api` with the provider's key set. It asks about 60 questions of three weights, stops at
the cap, needs no passwords, and prints credits, seconds and errors per kind. Without both guards
it refuses; on the demo provider it is a free dry run.

## Firewall in front of the website and API (WAF)

The API already limits requests per address and per business, but nothing filters traffic before it
arrives. Pick one (both have a free level, check the current limits before choosing):

1. **Vercel Firewall** (website only): Vercel project, Firewall tab, turn on the managed rules and
   "Attack Challenge Mode" as the emergency switch. No DNS change.
2. **Cloudflare in front of the domain** (website and API): add the domain to Cloudflare, move the
   name servers, set the records to proxied, SSL mode "Full (strict)", turn on Bot Fight Mode and the
   managed rules. Then add the Cloudflare address ranges to the trusted proxies and re-check
   `API_TRUST_FORWARDED_FOR` so rate limits still see the visitor's real address (ask Claude).

Check after: `curl -I https://<domain>` still returns the security headers, sign-in works, and a
test from a second network is not blocked.

## Company, bank account and insurance (A8)

Needed before the first paying customer, not before staging:

1. Register the business (or sole-trader file) and open a business bank account.
2. Put the real company name, number and VAT number in `packages/i18n/brand.json` (`legal`) and tell
   Claude, so invoices, the terms and the privacy policy stop using the fictitious ones.
3. Buy cyber and professional liability insurance; keep the policy number with the legal files.

## Professional penetration test (A12)

Do it after about 20 to 50 businesses or when a large customer asks for it (cost: thousands up to
tens of thousands of shekels). Give the tester a staging copy with demo data, the
[ASVS self-check](../reviews/go-live-asvs-self-check-2026-10.md) and the scope (website, API,
apps). Track every finding as a GitHub issue; fix the high ones before the next release.

## Decisions waiting for you (round 7 leftovers)

1. **Lawyer for the cancellation text (R33).** The MyBiz subscription cancellation wording and policy page are drafts. Have a lawyer review them before go-live.
2. **The 129 "solo" bundle price.** Decide how a bundle discount appears on the invoice; until then the price is not offered.
3. **OpenAI and Gemini prices.** Confirm them on the vendors' pricing pages before switching either provider on (see "Switching on a live AI provider").
4. **A monthly summary email** does not exist yet; decide if you want one (it would also carry the "My website" line).

## Still the owner's

Rotate `API_INTERNAL_TOKEN` (Render and Vercel), change the demo passwords, decide the AI credit
caps and #46/#47 (payments and invoicing stay disabled until the business operates), domain and
email provider, Sentry and uptime accounts, Apple Developer account if iOS is wanted, legal review.
