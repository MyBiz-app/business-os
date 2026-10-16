# Staging deployment

- Web: https://business-os-alpha-drab.vercel.app
- API: https://business-os-api-staging.onrender.com (`/health`, `/docs`)
- Expo apps on the web: https://mybiz-client-app.vercel.app (published by hand with [`deploy-apps-web.yml`](../../.github/workflows/deploy-apps-web.yml); it is in the API's `API_CORS_ORIGINS`). The old mybiz-business-app and mybiz-staff-app addresses only redirect to it

| Part | Provider | Deploys from | Config |
|---|---|---|---|
| Web (`apps/web`) | Vercel, functions in Frankfurt (`fra1`) | `main`, through GitHub Actions (the Hobby plan can't deploy a private organization repository from Git, so there are no PR previews) | Vercel project settings, [`apps/web/vercel.json`](../../apps/web/vercel.json), [`deploy-web.yml`](../../.github/workflows/deploy-web.yml) (needs the `VERCEL_TOKEN` secret in the `staging` environment) |
| Client app on the web (`apps/client-app`) | Vercel, static site | `main` | [`apps/client-app/vercel.json`](../../apps/client-app/vercel.json), [`apps/client-app/README.md`](../../apps/client-app/README.md) |
| API (`apps/api`) | Render, Frankfurt, free plan | `main` | [`render.yaml`](../../render.yaml) |
| Database + Auth | Supabase, Central EU (Frankfurt) | - | Supabase dashboard |
| Migrations | The API container on start (`alembic upgrade head` before uvicorn), and GitHub Actions | Every deploy; `main` (when migrations change) or by hand | [`Dockerfile`](../../apps/api/Dockerfile), [`migrate-staging.yml`](../../.github/workflows/migrate-staging.yml) |
| Demo data | GitHub Actions, by hand | - | [`seed-staging.yml`](../../.github/workflows/seed-staging.yml) |

All server-side parts run in Frankfurt: every page load makes several web → API → database
round trips, so keeping them in one region matters more than the user's distance to it.
Supabase and Render have no Israel region today; Frankfurt is close to Israel and inside the EU
(GDPR; Israel and the EU recognize each other's data protection as adequate).

The free Render plan sleeps after 15 minutes without traffic; the first request then takes
up to about a minute. Around the clock [`keep-api-awake.yml`](../../.github/workflows/keep-api-awake.yml)
pings it every 10 minutes so it stays awake (GitHub may delay scheduled runs; an outside pinger or a paid plan is the sturdier fix).

## Secrets and settings (never committed)

| Where | Name | Value |
|---|---|---|
| GitHub → Settings → Environments → `staging` | `STAGING_DATABASE_URL` | Supabase **Session pooler** connection string (port 5432), with the password filled in |
| Render → service → Environment | `API_DATABASE_URL` | Same as above |
| Render → service → Environment | `WEB_CONCURRENCY` (optional) | API worker processes, default 2. Keep workers × (`API_DB_POOL_SIZE` 5 + `API_DB_MAX_OVERFLOW` 10) under the database's connection limit |
| Render → service → Environment | `API_JWKS_URL` | `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json` |
| Vercel → project → Environment Variables | `NEXT_PUBLIC_SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| Vercel | `NEXT_PUBLIC_SUPABASE_KEY` | Supabase **publishable** key |
| Vercel | `NEXT_PUBLIC_API_URL` | Render service URL, e.g. `https://business-os-api-staging.onrender.com` |
| Vercel | `ENABLE_EXPERIMENTAL_COREPACK` | `1` (use the pnpm version pinned in `package.json`) |
| Vercel (web) | `NEXT_PUBLIC_CLIENT_APP_URL` | Optional: the client app's web address; the QR join page then offers "open in the browser" |
| Vercel (client app project) | `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_KEY` | Same values as the web's API URL, Supabase URL and publishable key |
| Render → service → Environment | `API_CORS_ORIGINS` | `["https://<client app address>"]`: the browser app calls the API directly |

Use the session pooler (IPv4, supports `SET LOCAL ROLE`), not the direct connection (IPv6
only) and not the transaction pooler (port 6543).

## One-time setup

1. **Supabase**: create project `business-os-staging` in Central EU (Frankfurt). Save the database
   password in a password manager.
   - Project Settings → JWT Keys: the current signing key must be asymmetric (ECC P-256). If
     it is the legacy HS256 secret, migrate to the new signing keys.
   - Authentication → URL Configuration: Site URL = the Vercel production URL; add
     `https://<vercel-domain>/**` to Redirect URLs (after step 4).
2. **GitHub**: create environment `staging` with secret `STAGING_DATABASE_URL`, then run
   *Actions → Migrate staging database → Run workflow*.
3. **Render**: *New → Blueprint*, pick this repository; enter `API_DATABASE_URL` and
   `API_JWKS_URL`. Check `https://<service>.onrender.com/health`.
4. **Vercel**: *Add New → Project*, import this repository, Root Directory `apps/web`; add the
   environment variables above; deploy.

## Health and rate limits

- `GET /health`: the process is up (Render's health check). `GET /health/ready`: the database
  answers too (503 when it doesn't); point uptime monitoring here.
- Rate limits per visitor (`app/core/rate_limit.py`): 20 public form posts and 120 public reads a
  minute (`/public/…`: join pages, quote links, inquiries, the contact form, file links), 600
  webhook calls, and a ceiling of 1,200 calls a minute for everything; over a limit the API
  answers 429 with `Retry-After`. On in every environment except local development
  (`API_RATE_LIMITS=false` turns them off). Behind Render's proxy `API_TRUST_FORWARDED_FOR=true`
  counts the right-most `X-Forwarded-For` address (the one Render appended, which a caller cannot
  forge). The web app names its visitors in `X-Visitor-Address`, believed only together with
  `X-Internal-Token` equal to `API_INTERNAL_TOKEN` (set the same value on Render and Vercel).
- The API refuses to start when `API_ENVIRONMENT` is not one of local/test/staging/production, or
  is local/test (the default) while the database is not on localhost.
- Counts are kept per API process by default. With more than one instance, set
  `API_RATE_LIMIT_REDIS_URL` (`redis://…`) and every instance counts in the same Redis
  (`RedisStore` in the same file; if Redis is unreachable it counts locally instead of failing).
  Not set anywhere yet: Redis is a paid service on Render, so it stays off until production.
- With `API_ENVIRONMENT=production` the API also refuses to start when `API_JWKS_URL`,
  `API_SECRETS_KEY`, `API_INTERNAL_TOKEN`, `API_WEB_URL`, `API_API_URL` or `API_CORS_ORIGINS`
  is missing or still points at localhost; the error names the missing ones. The background-job
  commands (`python -m app.jobs`) are not affected.

## Notes

- Supabase's built-in email sender only delivers to members of the Supabase organization and
  is heavily rate-limited, so other people cannot sign up or get sign-in codes. Configure
  custom SMTP (Authentication → Emails → SMTP Settings). For the prototype, Gmail works with
  no domain: host `smtp.gmail.com`, port `465`, username and sender = the Gmail address,
  password = its app password. Production should use a provider with its own domain.
- The default Supabase email templates work (links come back to `/auth/confirm?code=…`, in the
  same browser). Our own templates in `supabase/templates/` can be pasted into Authentication →
  Email Templates to allow confirming from any device.
- The API container migrates the database before it starts serving, so new code never runs
  against an old schema even when the GitHub runner for the migration workflow is slow (this
  happened once: the site errored until the queued workflow ran). Both paths take the same
  advisory lock, so they never migrate at the same time. Render keeps the previous version
  serving until the new one is healthy, so keep migrations backward compatible (add first,
  remove later).

## Notification emails (optional)

Client notifications (the app's Updates tab) can also go out by email. The hourly workflow
**Send notification emails on staging** does nothing until a provider is set.
Two providers are supported:

- **Gmail** (free, no domain; good for the prototype): a dedicated Gmail account with 2-Step
  Verification and an *app password* (https://myaccount.google.com/apppasswords). Gmail
  allows a few hundred messages a day and sends from that Gmail address.
- **Resend** (free tier: 3,000 emails a month): needs a verified sending domain (DNS records).

1. GitHub → repository → *Settings → Secrets and variables → Actions*:
   - **Secrets** → `EMAIL_API_KEY` = the Gmail app password (or the Resend API key)
   - **Variables** → `EMAIL_PROVIDER` = `gmail` (or `resend`), `EMAIL_FROM` = e.g.
     `MyBiz <mybiz.studio@gmail.com>` (or `MyBiz <updates@your-domain>`)
2. Run the workflow once by hand (*Actions → Send notification emails on staging → Run
   workflow*) and check its log.

Emails use the business's language and are sent once, within a day of the event; clients
without an email address are skipped. For local testing: `API_EMAIL_PROVIDER=log uv run
python -m app.jobs send-emails` prints instead of sending.

## Auth emails on staging

Supabase's built-in email only sends to the project's team members (a few per hour), so for
anyone else a sign-up **fails and no account is created**. Set up real email once:

1. **An SMTP sender.** Until there is a domain ([#48](https://github.com/MyBiz-app/business-os/issues/48)),
   a Gmail account with an *App Password* works (Google Account → Security → 2-Step
   Verification on → App passwords). Production: a domain with Resend or Amazon SES.
2. **Supabase → Authentication → Emails → SMTP Settings:** enable custom SMTP; host
   `smtp.gmail.com`, port `465`, username and sender = the Gmail address, password = the app
   password, sender name `MyBiz`. The password goes only into Supabase.
3. **Authentication → Rate Limits:** emails per hour, e.g. 100.
4. **Authentication → URL Configuration:** Site URL = the web address
   (`https://business-os-alpha-drab.vercel.app`); Redirect URLs: `<web address>/**` and the
   client app's address with `/**`.
5. **Authentication → Emails → Templates:** for *Confirm signup*, *Magic link* and *Reset
   password*, paste the subject and body from `supabase/config.toml` and
   `supabase/templates/*.html` (confirmation, magic_link, recovery). They link to
   `/auth/confirm` (works from any browser) and include the 6-digit code the client app asks for.
6. Keep **Sign In / Providers → Email → Confirm email** on.

*Actions → Create a demo account on staging* creates a confirmed sign-in (or updates its
password and name) for demo and team accounts. It takes a **bcrypt hash** of the password, never
the password: `python -c "import bcrypt; print(bcrypt.hashpw(b'...', bcrypt.gensalt()).decode())"`.
Then *Seed staging demo data* fills it: `owner` gives a business owner two businesses with
branches; `platform` gives a MyBiz owner a console to look at (six small customer businesses
with invoices, and a few contact requests). Both are safe to re-run with *replace*.

*Actions → Confirm an account on staging* confirms an account that was created but not
confirmed and creates its app profile; it fails with "No account" when the sign-up never
went through.
