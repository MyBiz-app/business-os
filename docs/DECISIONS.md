# Decisions Log

Status: `DECIDED` (owner approved) · `PROPOSED` (awaiting owner) · `OPEN` (needs discussion).
`DECIDED (delegated)` = owner approved Claude's recommendation without detailed review; revisit if
reality says otherwise. Pricing values (P4a–P4e) are placeholders and will be revisited before the pilot.
When a decision changes, update the row and note the date — do not delete history.

## Product

| # | Decision | Status |
|---|---|---|
| P1 | Vision: modular Business OS + AI Workforce for SMBs across many verticals (fitness, barbershops, salons, private clinics, ...). Core is vertical-agnostic; verticals are configuration packs. | DECIDED |
| P2 | Prototype vertical: boutique fitness studio (gym / pilates), on fake data. A real design partner (owner's friend) joins later. | DECIDED |
| P3 | Positioning: not reinventing the wheel — better design and UX, faster, AI built in, and cheaper. | DECIDED |
| P4 | Pricing: build-your-own plan. Pay only for selected modules, business size and usage; add/remove modules anytime. | DECIDED |
| P4a | Pricing presentation: per-vertical preset bundles + "customize"; positioned as "fair / pay for what you use", not "low-cost". | DECIDED (2026-10-03, delegated) |
| P4b | Every plan has a minimum Core price (floor) covering fixed per-tenant cost (mainly support). | DECIDED (2026-10-03, delegated) |
| P4c | AI and messaging: included allowance + metered overage. | DECIDED (2026-10-03, delegated) |
| P4d | Annual commitment discount; downgrades take effect at next billing period. | DECIDED (2026-10-03, delegated) |
| P4e | Explore payment-processing revenue share as a second revenue stream. | DECIDED (2026-10-03, delegated) |
| P5 | Markets: Israel → US → EU. Languages: Hebrew (RTL) + American English (LTR). Architecture supports more languages, currencies and time zones. | DECIDED |
| P6 | Client app: one shared app with dynamic per-business branding (App Store guideline 4.2.6). Standalone white-label apps = future premium. | DECIDED (2026-10-03, delegated) |
| P7 | Medical clinics vertical deferred (health-data regulation). | DECIDED (2026-10-03, delegated) |

## Technical

| # | Decision | Status |
|---|---|---|
| T1 | All code, identifiers, DB fields, commits and code docs in English. Hebrew only in translation resources and user content. | DECIDED |
| T2 | Monorepo: pnpm + Turborepo (TypeScript), uv (Python). | DECIDED (2026-10-03, delegated) |
| T3 | Backend: Python + FastAPI, SQLAlchemy 2, Alembic, Pydantic. OpenAPI → generated TS client. | DECIDED (2026-10-03, delegated) |
| T4 | Supabase from day one for Postgres + Auth + Storage. Tenant isolation in the API and via Postgres RLS. | DECIDED (2026-10-03, delegated) |
| T5 | Web: Next.js + TypeScript + Tailwind (logical properties) + shadcn/ui + next-intl. | DECIDED (2026-10-03, delegated) |
| T6 | Mobile: Expo + Expo Router + TypeScript. iOS builds via EAS cloud (owner on Windows + iPhone). | DECIDED (2026-10-03, delegated) |
| T7 | AI: Claude as primary, behind a provider-agnostic LLM gateway (model routing by task, swappable providers, future per-tenant model choice). | DECIDED |
| T8 | AI acts only through approved tools; sensitive actions → server-side Pending Actions, re-validated on confirm. | DECIDED |
| T9 | Scheduling: unified "session with capacity" (capacity 1 = appointment, N = class). | DECIDED (2026-10-03, delegated) |
| T10 | Analytics: semantic metrics layer; AI analyst queries metrics via tools, never free-form SQL. | DECIDED (2026-10-03, delegated) |
| T11 | Usage metering per tenant from day one. | DECIDED (2026-10-03, delegated) |
| T12 | Naming: `tenant` in code/DB, "business" in UI copy. End customers are `client` in code; vertical packs rename them in UI (member / customer / patient). | DECIDED (2026-10-03, delegated) |
| T13 | Identity: one global `user` (login) linked to many tenants as staff and/or client. A client record may exist without an app account (walk-ins). | DECIDED (2026-10-03, delegated) |

## Process

| # | Decision | Status |
|---|---|---|
| X1 | Prototype first: pricing details are not a blocker. Build the prototype on the decisions above and revisit pricing when the product is more mature. | DECIDED (2026-10-03) |
| X2 | Owner delegates day-to-day technical and product choices to Claude; significant changes are still proposed and logged here. | DECIDED (2026-10-03) |

## Open

| # | Question |
|---|---|
| O1 | Israeli payment provider for MVP (Cardcom / Grow / PayPlus / Tranzila / other). |
| O2 | Invoicing provider for MVP (Morning (Green Invoice) / iCount / EZcount / other). |
| O3 | Final brand name (repo uses neutral codename `business-os`). |

## Team & environment

- Builders: owner + Claude. Variable weekly capacity. A friend may join later.
- Owner dev machine: Windows + iPhone.
