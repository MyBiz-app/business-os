# 07 — Roadmap

Built in vertical slices: every sprint ends with something working end-to-end on web and mobile,
in Hebrew and English, light and dark. Sprint length is flexible (owner capacity varies).

## Phase 0 — Specification (now)

- [x] Review spec v1, record decisions
- [x] Owner approves `PROPOSED` decisions in `docs/DECISIONS.md` (delegated, 2026-10-03)
- [x] Screen list and user flows per side → [08-screens-and-flows.md](08-screens-and-flows.md)
- [ ] Finalize data model for Sprints 1–3 (done incrementally, per sprint)
- [ ] Owner local environment ready (see below)

## Phase 1 — Prototype

| Sprint | Goal |
|---|---|
| 1. Walking skeleton | Monorepo, CI, Supabase local, FastAPI + Next.js + Expo hello-world wired together; sign-up / verify / login; create tenant; tenant isolation + tests; i18n (he/en) + RTL + dark mode foundations; deploy to staging |
| 2. Core | Staff, roles & permissions, clients, services, locations, branding |
| 3. Schedule & booking | Sessions + recurrence, booking, capacity, waitlist, cancellation; branded client app (home, schedule, book) |
| 4. Plans & entitlements | Memberships, punch cards, freeze; scenario-based fake-data generator (months of history) |
| 5. Configurator & platform | Onboarding questionnaire + live pricing; module enablement; platform console (tenants, usage) |
| 6. Dashboard & AI | KPI dashboard on metrics layer; AI Q&A via read tools; first pending action with confirmation |

**Prototype done** = spec v1 §23 end-to-end scenario passes.

## Phase 2 — MVP (first real business)

Payment provider, invoicing provider, real email, data import, health declaration + signature,
production hardening (backups, monitoring, security review, legal docs).

## Phase 3+ — Pilot → 10 businesses → modules → AI Workforce → scale

As in spec v1 §26: pilot with 1–3 businesses, platform billing, CRM, WhatsApp, finance, marketing,
specialized agents, then additional vertical packs and markets (US, EU).

## Owner setup checklist (Windows + iPhone)

- [ ] Git — https://git-scm.com
- [ ] Node.js LTS — https://nodejs.org, then `npm i -g pnpm`
- [ ] Python 3.12 + uv — https://docs.astral.sh/uv
- [ ] Docker Desktop
- [ ] VS Code
- [ ] Expo Go on iPhone
- [ ] Free accounts: Supabase, Vercel, Expo
- [ ] Later: Anthropic Console (API key), Apple Developer ($99/yr) for store release
