# MyBiz (codename business-os)

An operating system for small and medium service businesses — studios and gyms, hair and beauty
salons, clinics, garages and more — with a branded app for each business's clients and an AI
assistant. Multi-tenant, modular (businesses build their own plan), Hebrew first, then English.

| Surface | Who uses it |
|---|---|
| Marketing website + sign-up journey | Business owners considering MyBiz |
| Business web app (CRM) | The business: owner, managers, front desk, staff |
| MyBiz console | MyBiz's own team: owners, managers, employees |
| Client app (Expo; also in the browser) | The businesses' clients — they never use a website |
| Business app (Expo) | Business owners and staff on the go: today, clients, numbers, check-in |
| MyBiz team app (Expo) | MyBiz's own team on the go: what needs attention, businesses, inbox |

## Status and documents

- **Product spec (v3):** [English](docs/spec/v3/spec.en.md) · [עברית](docs/spec/v3/spec.he.md) ·
  Word: [`docs/spec/MyBiz-Spec-en.docx`](docs/spec/MyBiz-Spec-en.docx),
  [`docs/spec/MyBiz-Spec-he.docx`](docs/spec/MyBiz-Spec-he.docx)
  (regenerate with `node scripts/spec-to-docx.cjs he|en`, needs the `docx` npm package).
- **Decisions:** [`docs/DECISIONS.md`](docs/DECISIONS.md) — every product and technical decision.
- **Status:** [`docs/STATUS.md`](docs/STATUS.md) — what is done, in progress and next; open work in GitHub issues.
- **Detailed v2 chapters:** [`docs/spec/v2/`](docs/spec/v2/README.md) (architecture, data model, AI).
- **Where we are:** the foundation is built (see the spec's roadmap). Now, one phase at a time:
  1 marketing website and sign-up journey → 2 business web app → 3 MyBiz console → 4 apps →
  go-live (real payments, invoicing, email, WhatsApp, AI key).
- Paid services run in clearly labeled demo / simulated modes until go-live.

## Repository layout

| Path | What |
|---|---|
| `apps/web` | Business web app: Next.js, Tailwind, next-intl (he / en), light / dark |
| `apps/api` | Backend API: Python 3.13, FastAPI, managed with uv |
| `apps/mobile` | Client app: Expo (SDK 57) + Expo Router, shared translations, light / dark, RTL |
| `apps/business-app` | Business app for owners and staff on the go (Expo) |
| `apps/staff-app` | MyBiz team app (Expo) |
| `packages/i18n` | Shared translations (he / en) and locale helpers for the web and the apps |
| `packages/app-kit` | What the three apps share: API client, design tokens, components, providers |
| `packages/verticals` | The industry catalog: categories and sub-categories, shared by the API, the web and the apps ([how to add one](docs/verticals.md)) |
| `docs/` | Spec (v3 overview + Word files, v2 chapters) and decision log |
| `scripts/` | Developer machine setup, spec → Word |

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

The apps run separately: `pnpm --filter mobile exec expo start --web` (clients, port 8081),
`pnpm --filter business-app exec expo start --web --port 8082` (the business),
`pnpm --filter staff-app exec expo start --web --port 8083` (the MyBiz team).

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

## Troubleshooting

**The sign-in code doesn't arrive (client app) / no confirmation email.** Local emails never
leave your computer: open the test mailbox at http://127.0.0.1:54324. The email texts (a
6-digit code for the client app) are applied when Supabase starts, so after pulling changes
restart it: `pnpm db:stop` then `pnpm db:start`.

**Windows: `pnpm db:start` fails with `spawn UNKNOWN`.** Smart App Control blocks the
unsigned `supabase.exe`. Keep Smart App Control on (it can't be turned back on without
reinstalling Windows) and run the Supabase CLI from WSL instead; Docker Desktop is shared:

1. PowerShell (once): `wsl --install -d Ubuntu`, restart, open "Ubuntu" and create a user.
2. Docker Desktop → Settings → Resources → WSL integration → enable Ubuntu.
3. In Ubuntu:

   ```bash
   mkdir -p ~/bin
   curl -fsSL https://github.com/supabase/cli/releases/latest/download/supabase_linux_amd64.tar.gz | tar -xz -C ~/bin supabase
   cd /mnt/c/dev/business-os
   ~/bin/supabase start     # ~/bin/supabase stop to stop
   ```

Everything else (`pnpm db:migrate`, `pnpm dev`, `pnpm dev:app`) runs in PowerShell as usual.

## Checks

```bash
pnpm lint        # ESLint + Ruff
pnpm typecheck   # TypeScript
pnpm test        # pytest (needs `pnpm db:start`) + translation checks
pnpm build       # production build
```

CI runs all of them on every pull request.
