# 07 — Roadmap

Built in vertical slices: every sprint ends with something working end-to-end on web and mobile,
in Hebrew and English, light and dark. Sprint length is flexible (owner capacity varies).

## Phase 0 — Specification (now)

- [x] Review spec v1, record decisions
- [x] Owner approves `PROPOSED` decisions in `docs/DECISIONS.md` (delegated, 2026-10-03)
- [x] Screen list and user flows per side → [08-screens-and-flows.md](08-screens-and-flows.md)
- [ ] Finalize data model for Sprints 1–3 (done incrementally, per sprint)
- [x] Owner local environment ready (see below)

## Phase 1 — Prototype

| Sprint | Goal |
|---|---|
| 1. Walking skeleton | Monorepo, CI, Supabase local, FastAPI + Next.js + Expo hello-world wired together; sign-up / verify / login; create tenant; tenant isolation + tests; i18n (he/en) + RTL + dark mode foundations; deploy to staging |
| 2. Core | Staff, roles & permissions, clients, services, locations, branding |
| 3. Schedule & booking | Sessions + recurrence, booking, capacity, waitlist, cancellation; branded client app (home, schedule, book) |
| 4. Plans & entitlements | Memberships, punch cards, freeze; scenario-based fake-data generator (months of history) |
| 5. Configurator & platform | Onboarding questionnaire + live pricing; module enablement; platform console (tenants, usage) |
| 6. Dashboard & AI | KPI dashboard on metrics layer; AI Q&A via read tools; first pending action with confirmation |

**Prototype done** = spec v1 §23 end-to-end scenario passes. ✅ Automated in `e2e/dod.py` (with axe accessibility checks, Hebrew/light and English/dark); still open: the same run against staging with real email (needs the production email provider).

## Phase 2 — MVP (first real business)

Payment provider, invoicing provider, real email, data import, health declaration + signature,
production hardening (backups, monitoring, security review, legal docs).

## Phase 3+ — Pilot → 10 businesses → modules → AI Workforce → scale

As in spec v1 §26: pilot with 1–3 businesses, platform billing, CRM, WhatsApp, finance, marketing,
specialized agents, then additional vertical packs and markets (US, EU).

## Sprint 1 progress

- [x] Monorepo (pnpm + Turborepo), CI on pull requests
- [x] API hello-world (FastAPI, `/health`, tests)
- [x] Web hello-world (Next.js): he / en, RTL / LTR, light / dark, calls the API
- [x] Mobile hello-world (Expo): he / en with RTL, light / dark, calls the API (owner to verify on iPhone)
- [x] Shared translations package (`packages/i18n`) used by web and mobile
- [x] Supabase local + database migrations (Alembic) + RLS
- [x] Sign up / verify email / log in / reset password (web)
- [x] Create business (tenant) + dashboard shell + business switcher + tenant-isolation tests
- [x] Mobile sign in (delivered in Sprint 3, with the client app)
- [x] Deploy to staging: web https://business-os-alpha-drab.vercel.app · API https://business-os-api-staging.onrender.com

## Sprint 2 progress

- [x] Business navigation shell (side navigation)
- [x] Permissions model (permission keys in code, system roles)
- [x] Clients: list, search, create, edit, profile (vertical terminology, e.g. "members")
- [x] Services (duration, capacity, price, color) and locations with rooms
- [x] Staff: invite by link, roles, remove; last-owner and owner-only guards
- [x] Custom roles: API + role editor screen + role picker on the team page; the UI follows each member's effective permissions (navigation, dashboard, pages)
- [ ] Real invitation emails (with the production email provider)
- [x] Business settings (name, language, time zone, currency) and branding (color with contrast-safe text, logo)

## Sprint 3 progress

- [x] Sessions: one-off and weekly series (expanded in the business time zone, DST-safe), edit or cancel one occurrence
- [x] Weekly schedule screen (staff web), new-session form with room and instructor
- [x] Bookings (staff web): book a client, capacity, FIFO waitlist with auto-promotion, late-cancellation window, check-in / no-show, client booking history
- [x] Client app: email-code sign in, join a business by code / QR, branded home, schedule, book / waitlist / cancel, my bookings, profile (language, theme, switch business)
- [x] Staff web: join code + printable QR; public join page
- [ ] Background job to extend weekly series beyond their first 12–26 weeks

## Sprint 4 progress

- [x] Plans catalog (memberships, punch cards) with vertical-pack defaults
- [x] Sell a plan to a client (simulated, idempotent payment), freeze, cancel
- [x] Bookings use entitlements (credits, validity, freezes); client app requires a valid plan
- [x] Client app: "My plans" with remaining entries and validity
- [x] Demo data generator (`python -m app.seed`) + "Create demo studio on staging" workflow
- [ ] Client self-purchase in the app (needs a payment provider, O1)

## Sprint 5 progress

- [x] Modules catalog + Core tiers (placeholder prices), presets, dependency rules
- [x] Onboarding questionnaire → recommended plan → configurator with live price
- [x] Modules & plan page in settings; features gated by module (client app, AI, AI actions)
- [x] Platform console: businesses, modules, usage (AI credits), per-business page
- [ ] Platform billing (subscriptions, proration, price versions) and audited support access

## Sprint 6 progress

- [x] Metrics layer (`app/metrics.py`) + `/metrics` API with previous-period comparison and weekly series
- [x] KPI dashboard (tiles, revenue and check-ins per week, today's sessions)
- [x] AI assistant: Q&A through read tools + metrics; booking / cancelling as confirmable pending actions; audit log; AI usage metering
- [ ] AI eval set (Hebrew + English business questions) run when prompts or models change

## Owner setup checklist (Windows + iPhone)

- [ ] Git — https://git-scm.com
- [ ] Node.js LTS — https://nodejs.org, then `npm i -g pnpm`
- [ ] uv — https://docs.astral.sh/uv (installs Python 3.13 for the project)
- Automated: `scripts/setup-windows.ps1` installs pnpm, uv, Python and clones the repo
- [ ] Docker Desktop
- [ ] VS Code
- [ ] Expo Go on iPhone
- [ ] Free accounts: Supabase, Vercel, Expo
- [ ] Later: Anthropic Console (API key), Apple Developer ($99/yr) for store release
