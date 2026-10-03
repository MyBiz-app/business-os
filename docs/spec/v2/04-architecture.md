# 04 — Architecture

## Stack

| Layer | Choice |
|---|---|
| Monorepo | pnpm workspaces + Turborepo (TS), uv (Python) |
| Backend API | Python 3.13, FastAPI, SQLAlchemy 2 (psycopg 3), Alembic (hand-written SQL migrations), Pydantic v2 |
| Background jobs | Postgres-backed queue (no Redis); introduced when first needed (reminders / notifications, Sprint 3) |
| Database | PostgreSQL (Supabase), Row-Level Security as defense-in-depth |
| Auth | Supabase Auth (email + verification, password reset; later Google/Apple, MFA). API verifies Supabase ES256 JWTs via JWKS |
| Storage | Supabase Storage (logos, images, signed forms) |
| Web | Next.js (App Router), TypeScript, Tailwind, shadcn/ui, next-intl |
| Mobile | Expo, Expo Router, TypeScript; EAS for builds |
| API contract | OpenAPI from FastAPI → `packages/api-client` (openapi-typescript + openapi-fetch); CI fails if it is out of date |
| AI | LLM gateway in the API; Claude primary (see [06-ai](06-ai.md)) |
| Email | Mailpit (dev), Resend or Postmark (prod) |
| Observability | Sentry (errors), PostHog (product analytics, feature flags) |
| CI/CD | GitHub Actions |
| Hosting | Vercel (web), container host for API (`apps/api/Dockerfile`; provider chosen for staging), Supabase (EU region) |

## Monorepo layout

```
apps/
  web/            # Next.js: business dashboard (later: platform console, public booking pages)
  mobile/         # Expo: client app (+ owner quick actions later)
  api/            # FastAPI: domain, auth, tenancy (later: AI gateway, jobs); Alembic migrations
packages/
  api-client/     # TS client generated from the API's OpenAPI schema
  i18n/           # shared translations (he, en) + locale helpers (later: vertical terminology)
supabase/         # local Supabase config and email templates
docs/
```

Later, as needed: `packages/ui-tokens` (shared design tokens), `packages/config` (shared lint/TS config).

## Tenancy

- Every tenant-scoped table has `tenant_id`. The API reads the tenant from the `X-Tenant-Id`
  header and verifies the user's membership in it (403 otherwise).
- Every transaction runs as role `app_api` (no RLS bypass) with `app.user_id` and
  `app.tenant_id` set; `app.current_tenant_id()` only returns a tenant the user belongs to.
- App tables live in schema `app`, which Supabase does not expose to browsers.
- Automated tests assert that tenant A can never read or write tenant B data, through the API
  and directly in Postgres.

## Internationalization, theming, accessibility

- All user-facing strings in `packages/i18n`; `he` and `en` from day one.
- Web: `dir="rtl|ltr"` on `<html>`; Tailwind logical utilities (`ms-*`, `me-*`, `ps-*`, `pe-*`).
- Mobile: RTL via `I18nManager`; switching direction requires an app reload — handled in the
  language switch flow.
- Semantic color tokens (`surface`, `on-surface`, `primary`, ...) in light and dark; tenant brand
  colors mapped onto tokens with automatic contrast checks.
- Dates, numbers and currency formatted with `Intl` per locale; tenant time zone for display.

## Environments

| Env | Purpose |
|---|---|
| local | Docker (Postgres via Supabase CLI, Redis, Mailpit) |
| staging | Pre-release, seeded with fake data |
| production | Real tenants |

## Security baseline

TLS everywhere, no plaintext passwords (Supabase Auth), RLS + API authorization, audit log,
rate limiting, secrets in provider secret stores, backups, Sentry alerts, dependency scanning in CI,
no card data stored (provider tokens only), data minimization for AI.
