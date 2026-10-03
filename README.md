# business-os

> Codename. Final brand name TBD.

A modular, multi-tenant **Business Operating System** for small and medium businesses, with an
**AI Workforce** (finance, marketing, booking, CRM and analyst agents) that answers questions and
performs confirmed actions.

- **Markets:** Israel first (Hebrew, RTL), then US / EU (American English, LTR)
- **First vertical:** boutique fitness studios; designed to extend to barbershops, salons, clinics and more
- **Pricing model:** build-your-own plan — pay only for the modules, size and usage you need

## Status

Phase 1, Sprint 1 (walking skeleton). Spec: [`docs/spec/v2/`](docs/spec/v2/README.md) ·
Decisions: [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Repository layout

| Path | What |
|---|---|
| `apps/web` | Business web app: Next.js, Tailwind, next-intl (he / en), light / dark |
| `apps/api` | Backend API: Python 3.13, FastAPI, managed with uv |
| `packages/` | Shared TypeScript packages (later: API client, UI, config) |
| `docs/` | Spec and decision log |
| `scripts/` | Developer machine setup |

## Run locally

Prerequisites: Git, Node.js 22+, pnpm, uv, Docker. On Windows, `scripts/setup-windows.ps1`
installs what is missing.

```bash
pnpm install                        # JavaScript dependencies (all apps)
cd apps/api && uv sync && cd ../..  # Python dependencies
pnpm dev                            # starts API (port 8000) and web (port 3000)
```

Open http://localhost:3000. API docs: http://localhost:8000/docs.

## Checks

```bash
pnpm lint        # ESLint + Ruff
pnpm typecheck   # TypeScript
pnpm test        # pytest
pnpm build       # production build
```

CI runs all of them on every pull request.
