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

## Production settings (the API will not start without the first six)

| Variable | Value |
|---|---|
| `API_ENVIRONMENT` | `production` |
| `API_DATABASE_URL` | Supabase session pooler string, with the password |
| `API_JWKS_URL` | `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json` |
| `API_SECRETS_KEY` | A Fernet key (encrypts businesses' provider secrets); keep a copy in the secret store |
| `API_INTERNAL_TOKEN` | A long random value, the same on Render and Vercel |
| `API_WEB_URL`, `API_API_URL` | The public addresses (not localhost) |
| `API_CORS_ORIGINS` | JSON list of the real web and app origins (not localhost) |
| `API_TRUST_FORWARDED_FOR` | `true` behind Render's proxy |
| `API_RATE_LIMIT_REDIS_URL` | Optional; only when running more than one API instance (**off**) |
| `API_ANTHROPIC_API_KEY`, `API_EMAIL_*` | Optional until the AI assistant and real email are wanted |

## Still the owner's

Rotate `API_INTERNAL_TOKEN` (Render and Vercel), change the demo passwords, decide the AI credit
caps and #46/#47 (payments and invoicing stay disabled until the business operates), domain and
email provider, Sentry and uptime accounts, Apple Developer account if iOS is wanted, legal review.
