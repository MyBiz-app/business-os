# 04 — Architecture

## Stack

| Layer | Choice |
|---|---|
| Monorepo | pnpm workspaces + Turborepo (TS), uv (Python) |
| Backend API | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Background jobs | ARQ (Redis) or a Postgres-backed queue — decided in Sprint 1 |
| Database | PostgreSQL (Supabase), Row-Level Security as defense-in-depth |
| Auth | Supabase Auth (email + verification, password reset, Google/Apple, MFA). API verifies Supabase JWT |
| Storage | Supabase Storage (logos, images, signed forms) |
| Web | Next.js (App Router), TypeScript, Tailwind, shadcn/ui, next-intl |
| Mobile | Expo, Expo Router, TypeScript; EAS for builds |
| API contract | OpenAPI from FastAPI → generated TS client shared by web and mobile |
| AI | LLM gateway in the API; Claude primary (see [06-ai](06-ai.md)) |
| Email | Mailpit (dev), Resend or Postmark (prod) |
| Observability | Sentry (errors), PostHog (product analytics, feature flags) |
| CI/CD | GitHub Actions |
| Hosting | Vercel (web), container host for API (Render / Fly / Cloud Run), Supabase (EU region) |

## Monorepo layout (target)

```
apps/
  web/            # Next.js: business dashboard, platform console, public booking pages
  mobile/         # Expo: client app (+ owner quick actions later)
services/
  api/            # FastAPI: domain, auth, tenancy, AI gateway, jobs
packages/
  api-client/     # generated TS client from OpenAPI
  i18n/           # shared translation resources (en, he) + vertical terminology
  ui-tokens/      # design tokens: semantic colors, spacing, typography
  config/         # shared eslint/tsconfig/prettier
docs/
```

## Tenancy

- Every tenant-scoped table has `tenant_id`. The API resolves the tenant from the request
  (header / subdomain) and verifies the user's membership in it.
- Each request sets `app.tenant_id` on the DB session; RLS policies filter on it.
- Automated tests assert that tenant A can never read or write tenant B data.

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
