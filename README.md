# business-os

> Codename. Final brand name TBD.

A modular, multi-tenant **Business Operating System** for small and medium businesses, with an
**AI Workforce** (finance, marketing, booking, CRM and analyst agents) that answers questions and
performs confirmed actions.

- **Markets:** Israel first (Hebrew, RTL), then US / EU (American English, LTR)
- **First vertical:** boutique fitness studios; designed to extend to barbershops, salons, clinics and more
- **Pricing model:** build-your-own plan — pay only for the modules, size and usage you need

## Status

Prototype complete (Phase 1); Phase 2 (MVP) in progress. Spec: [`docs/spec/v2/`](docs/spec/v2/README.md) ·
Decisions: [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Repository layout

| Path | What |
|---|---|
| `apps/web` | Business web app: Next.js, Tailwind, next-intl (he / en), light / dark |
| `apps/api` | Backend API: Python 3.13, FastAPI, managed with uv |
| `apps/mobile` | Mobile app: Expo (SDK 57) + Expo Router, shared translations, light / dark, RTL |
| `packages/i18n` | Shared translations (he / en) and locale helpers for web and mobile |
| `docs/` | Spec and decision log |
| `scripts/` | Developer machine setup |

## Run locally

Prerequisites: Git, Node.js 22+, pnpm, uv, Docker. On Windows, `scripts/setup-windows.ps1`
installs what is missing.

```bash
pnpm install                        # JavaScript dependencies (all apps)
cd apps/api && uv sync && cd ../..  # Python dependencies
pnpm db:start                       # local Supabase in Docker (first run downloads images)
pnpm db:migrate                     # apply database migrations
pnpm dev                            # starts API (port 8000) and web (port 3000)
```

| URL | What |
|---|---|
| http://localhost:3000 | Web app |
| http://localhost:8000/docs | API docs |
| http://127.0.0.1:54323 | Supabase Studio (browse the database) |
| http://127.0.0.1:54324 | Test mailbox (sign-up and password-reset emails) |

`pnpm db:stop` stops Supabase; data is kept for the next start.

Demo data: sign up at http://localhost:3000 (the confirmation email arrives in the test
mailbox), then fill your account with a demo studio with months of history:

```bash
pnpm db:seed --owner-email you@example.com
```

Without an AI key the assistant runs in demo mode; payments are simulated (test card) and
receipts are samples.

The client app in the browser (second terminal), at http://localhost:8081:

```bash
pnpm dev:app
```

Mobile (in a second terminal), with the phone on the same Wi-Fi as the computer:

```bash
pnpm dev:mobile                     # scan the QR code with the iPhone camera → opens in Expo Go
```

## Checks

```bash
pnpm lint        # ESLint + Ruff
pnpm typecheck   # TypeScript
pnpm test        # pytest (needs `pnpm db:start`) + translation checks
pnpm build       # production build
```

CI runs all of them on every pull request.
