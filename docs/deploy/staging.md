# Staging deployment

| Part | Provider | Deploys from | Config |
|---|---|---|---|
| Web (`apps/web`) | Vercel | `main` (previews for every PR) | Vercel project settings |
| API (`apps/api`) | Render, Frankfurt, free plan | `main` | [`render.yaml`](../../render.yaml) |
| Database + Auth | Supabase, Central EU (Frankfurt) | — | Supabase dashboard |
| Migrations | GitHub Actions | `main` (when migrations change) or by hand | [`migrate-staging.yml`](../../.github/workflows/migrate-staging.yml) |

The free Render plan sleeps after 15 minutes without traffic; the first request then takes
up to about a minute.

## Secrets and settings (never committed)

| Where | Name | Value |
|---|---|---|
| GitHub → Settings → Environments → `staging` | `STAGING_DATABASE_URL` | Supabase **Session pooler** connection string (port 5432), with the password filled in |
| Render → service → Environment | `API_DATABASE_URL` | Same as above |
| Render → service → Environment | `API_JWKS_URL` | `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json` |
| Vercel → project → Environment Variables | `NEXT_PUBLIC_SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| Vercel | `NEXT_PUBLIC_SUPABASE_KEY` | Supabase **publishable** key |
| Vercel | `NEXT_PUBLIC_API_URL` | Render service URL, e.g. `https://business-os-api-staging.onrender.com` |
| Vercel | `ENABLE_EXPERIMENTAL_COREPACK` | `1` (use the pnpm version pinned in `package.json`) |

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

## Notes

- Supabase's built-in email sender only delivers to members of the Supabase organization and
  is heavily rate-limited. Fine for staging; production needs a real email provider (Resend /
  Postmark) configured as custom SMTP.
- The default Supabase email templates work (links come back to `/auth/confirm?code=…`, in the
  same browser). Our own templates in `supabase/templates/` can be pasted into Authentication →
  Email Templates to allow confirming from any device.
- On a push to `main` the migration workflow and the Render deploy run in parallel. Keep
  migrations backward compatible (add first, remove later) so either order works.
