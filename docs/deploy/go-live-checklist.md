# Go-live checklist

Copy of section 1 of the 2026-10-11 remaining-work plan, plus how each item is switched on in
code. Everything marked **off** is built and disabled; nothing that costs money turns on by itself.
Tick items here as they are done (and record cost decisions in `docs/DECISIONS.md`).

## Blockers

| # | Item | State | To switch on |
|---|---|---|---|
| P0-1 | Production environment: Vercel Pro, Render Starter or above, Supabase Pro, backups. About $55-75 a month | Owner approves first | Create the services, then set the variables below |
| P0-2 | Background jobs as Render cron (GitHub schedules skip runs) | Built, **off** | Stop the staging GitHub schedules for the same database, then Render → New → Blueprint → `render.production.yaml`. Set `API_DATABASE_URL` and `API_SECRETS_KEY` when asked |
| P0-3 | Monitoring: JSON logs and request ids exist; error tracking (Sentry) and an uptime monitor do not | Needs an account | Point the uptime monitor at `/health/ready`; add Sentry |
| P0-7 | Files in object storage | Built | `API_STORAGE_PROVIDER=supabase` and `API_STORAGE_SETTINGS` (see `docs/STATUS.md`) |
| P0-8 | Supabase Auth settings applied from CI | Built | Add `SUPABASE_ACCESS_TOKEN` to the GitHub environment; see `auth-settings.md` |
| P0-9 | Legal text from a lawyer (privacy policy, terms, DPA, cookie banner); account closure and 90-day deletion | Closure built; text open | Lawyer; real deletion is enabled with `--apply` on `delete-closed-businesses` |
| B4 | Backups and a restore drill | After P0-1 | Follow `restore-runbook.md` and fill in its drill table |
| B5 | Test cards refused in production | Done (#191) | Nothing |
| GL3-a | `simulate-payment` returns 404 in production; uploads are checked by their bytes and by the storage allowance (logo, cover, branch logo, AI agent picture, documents, files area, migration files) | Done | Nothing |
| GL3-b | Virus scanning of uploads (ClamAV) | Built, **off** (costs about $7 a month for the scanner service) | See "Switching on virus scanning" below |

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
| `API_RATE_LIMIT_REDIS_URL` | Optional; only when running more than one API instance (**off**) |
| `API_ANTHROPIC_API_KEY`, `API_EMAIL_*` | Optional until the AI assistant and real email are wanted |

## Switch-on steps that need a paid plan (GL1)

| Item | State | To switch on |
|---|---|---|
| Leaked-password check (Supabase) | Built, **off** (needs the Pro plan) | Upgrade the Supabase project, then run the workflow "Apply Supabase auth settings" with "apply" and "paid_plan" ticked. Checks the password against known leaks on sign-up and password change |
| Server-side session timeouts (Supabase `[auth.sessions]`) | Not used | The web app signs out after 12 hours idle and the app after 30 days by itself. A server-side limit is a Pro setting if wanted later |

Two-step sign-in is free and on: turn it on for your own account first (Account → Account security),
and for every provider account (GitHub, Supabase, Render, Vercel, Google, Apple).

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

## Switching on sign-in removal (account deletion)

"Delete my account" in the apps empties the person's profile and disconnects them. To also delete
their login at Supabase Auth, set `API_SUPABASE_URL` (the project URL) and
`API_SUPABASE_SERVICE_KEY` (the service role key, from Supabase, Settings, API) as secrets on
the API host. Never put the key in the repository or in the apps. Without them the account can
no longer be used (the API answers `account_deleted`), but the login row stays at Supabase.

## Still the owner's

Rotate `API_INTERNAL_TOKEN` (Render and Vercel), change the demo passwords, decide the AI credit
caps and #46/#47 (payments and invoicing stay disabled until the business operates), domain and
email provider, Sentry and uptime accounts, Apple Developer account if iOS is wanted, legal review.
