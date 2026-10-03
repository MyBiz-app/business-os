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
| T3 | Backend: Python 3.13 (pinned per project via uv, no global Python needed) + FastAPI, SQLAlchemy 2, Alembic, Pydantic. OpenAPI → generated TS client. | DECIDED (2026-10-03, delegated) |
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
| T14 | Web locale comes from the user's choice (cookie), then browser language, then Hebrew. App URLs are not locale-prefixed; public marketing / booking pages may add prefixes later. | DECIDED (2026-10-03, delegated) |
| T15 | Tooling versions: Node 22+ (owner on 24), pnpm 12, Python 3.13 via uv, Next.js 16, Expo SDK 57. Line endings LF in the repo (`.gitattributes`). | DECIDED (2026-10-03, delegated) |
| T16 | Database schema is owned by Alembic migrations (hand-written SQL) in `apps/api`. Supabase owns only its own schemas (auth, storage). App tables live in schema `app`, which Supabase does not expose to browsers. | DECIDED (2026-10-03, delegated) |
| T17 | Tenant isolation: the API runs every transaction as role `app_api` (no RLS bypass) with `app.user_id` / `app.tenant_id` set per transaction. `app.current_tenant_id()` returns a tenant only if the user is a member, so a forged tenant id grants nothing. Isolation is tested at both API and database level. | DECIDED (2026-10-03, delegated) |
| T18 | Auth: Supabase Auth issues tokens (ES256); the API verifies them against Supabase's JWKS. Clients never query app tables directly; all data goes through the API. | DECIDED (2026-10-03, delegated) |
| T19 | Background jobs: a Postgres-backed queue instead of Redis (one less service to run and pay for). Added when first needed. | DECIDED (2026-10-03, delegated) |
| T20 | Typed API contract: `packages/api-client` is generated from FastAPI's OpenAPI schema; web (and later mobile) call the API only through it. | DECIDED (2026-10-03, delegated) |
| T21 | Staging hosting: Vercel (web), Render free plan in Frankfurt (API, Docker), Supabase Central EU. Migrations via a GitHub Actions workflow. Revisit API host (e.g. Cloud Run) before production. | DECIDED (2026-10-03) |
| T22 | Permissions: keys defined in code (`app/permissions.py`), system roles map to key sets; the API checks them per endpoint, the web mirrors them only to hide unavailable actions. Custom roles stored in the DB come later. | DECIDED (2026-10-03, delegated) |
| T23 | Vertical terminology lives in translations under `terms.<vertical>.*` (e.g. fitness: "Members" / "מתאמנים"); screens pick the tenant's vertical, never branch on it. | DECIDED (2026-10-03, delegated) |
| T24 | Staff invitations are one-time links (7 days, only a SHA-256 hash stored) that the inviter shares; accepting requires the signed-in email to match. Emailing them waits for the production email provider. | DECIDED (2026-10-03, delegated) |
| T25 | Prototype stores the business logo in Postgres (≤512 KB PNG/JPEG/WebP, type checked by file content, served publicly by the API with immutable caching). Moves to Supabase Storage when media grows beyond logos. | DECIDED (2026-10-03, delegated) |
| T26 | Brand color replaces the product's primary color inside the business's area; text on it is black or white, whichever has the higher WCAG contrast. | DECIDED (2026-10-03, delegated) |
| T27 | Schedule model: `sessions` are concrete occurrences (timestamptz, UTC); a weekly `session_series` stores local wall-clock time and is expanded in the business time zone when created (default 12 weeks, max 26) — editing one occurrence never touches the others. Composite foreign keys keep every reference inside the tenant. | DECIDED (2026-10-03, delegated) |
| T28 | Bookings: one `bookings` row per client per session with status `booked` / `waitlisted` / `checked_in` / `no_show` / `cancelled` (cancelled rows are kept as history). Capacity is enforced under a row lock on the session; the waitlist is FIFO and is promoted automatically when a spot opens in an upcoming session (cancellation or more capacity). Cancelling inside the business's late-cancellation window (vertical-pack default: 2 h for fitness) still frees the spot but is flagged `late_cancel` for plans in Sprint 4. New permission `bookings.manage` for every system role, so instructors can check members in. | DECIDED (2026-10-03, delegated) |
| T29 | Client access: end customers are `clients` linked to a signed-in user (`clients.user_id`). They select a business like staff do (X-Tenant-Id), but are not members, so staff policies never apply; narrow client RLS policies expose the business's catalog and schedule and only the client's own row and bookings. Capacity, waitlist position and promotion — which involve other clients' bookings — run in SECURITY DEFINER functions shared by staff and client requests. | DECIDED (2026-10-03, delegated) |
| T30 | Client sign-in is passwordless (6-digit email code, Supabase OTP); businesses get a short join code (8 characters, no look-alikes) and a printable QR that opens a public `/join/<code>` page. Joining claims an existing client record with the same verified email, otherwise creates one. One shared client app (MyBiz) shows each business's branding. | DECIDED (2026-10-03, delegated) |
| T31 | Plans & entitlements: `plans` (membership = unlimited within validity; punch card = credits + validity) and `entitlements` (a client's purchase, with the plan's terms copied at sale). Credits are derived from the bookings that use the entitlement (a cancellation in time returns the credit; a late one does not). Freezes pause given days and extend the end date. A booking uses an unlimited membership first, then the card that expires soonest, serialized per client. The client app requires a valid plan when the business says so (vertical-pack default: yes for fitness); staff can always book (walk-ins), and the roster shows "no plan". Sales are idempotent and record a simulated payment until a provider is chosen (O1). New permission `sales.manage` (owner, manager, front desk). | DECIDED (2026-10-03, delegated) |
| T32 | Demo data: `python -m app.seed` builds a deterministic demo studio (170 clients, weekly timetable, months of sales and bookings, churn, no-shows, late cancellations, waitlists). A manual GitHub workflow runs it on staging for a given owner. A test checks capacity and credit invariants on the generated data. | DECIDED (2026-10-03, delegated) |
| T33 | Metrics layer: named metrics (revenue, active clients, new clients, plans sold, check-ins, occupancy, no-show rate, late-cancellation rate, sessions held) defined once in `app/metrics.py` over local-date periods, with comparison to the previous period and weekly series. Dashboards and the AI use only these. KPIs need the new `reports.read` permission (owner, manager); everyone sees today's sessions. Charts are plain accessible SVG (single series, hover/focus tooltip, table view) — no chart library. | DECIDED (2026-10-03, delegated) |
| T34 | AI assistant (first slice): one LLM gateway (`app/ai/gateway.py`, provider adapter; Claude Opus 5.5 with server-side refusal fallback, medium effort, prompt caching). Read tools (clients, schedule, roster, metrics, plans) and write tools that only create pending actions (book, cancel), all run with the requesting user's permissions; tools a role lacks are not offered. Pending actions are confirmed by id in the UI (never "yes" to the model), re-validated (requester, permission, hash, 15-minute expiry), executed once, and written to `audit_log`. Every model call records `usage_events` (`ai_credits`, 1 credit = 1 US cent of model cost). Conversations are stored append-only and private to their user. Without `API_ANTHROPIC_API_KEY` the assistant shows "not set up yet". New permission `ai.use` (owner, manager, front desk). | DECIDED (2026-10-03, delegated) |
| T35 | Modules & configurator: modules (client app, AI Basic / AI Pro, extra locations; CRM, analytics, agents, WhatsApp shown as "coming soon") and Core priced by active-client tier are defined in code (`app/modules.py`, placeholder prices per currency). Onboarding asks five questions, the server recommends a preset (starter / growing / AI-powered), the owner adjusts with a live price, and the API validates dependencies. Features are gated server-side by module: client app (joining and all client endpoints), assistant (any AI tier), assistant actions (AI Pro). Existing businesses kept everything (client app + AI Pro). Billing stays simulated. | DECIDED (2026-10-03, delegated) |
| T36 | Platform console: platform admins (granted by hand / a staging workflow, never via the API) see all businesses, their modules, members, clients, bookings and AI usage through SECURITY DEFINER functions that check `is_platform_admin()`. Admin status gives no access to a business's own data; audited support access is a later feature. | DECIDED (2026-10-03, delegated) |
| T37 | Custom roles: a business can define named roles as switches over the permission keys (`tenant_roles`); a member with a custom role has exactly its permissions (system role `staff` underneath). Owners always keep the full owner role. Nobody can grant permissions they do not hold themselves, change their own role (except an owner stepping down while another owner remains), or make owners unless they are one. Requests carry the member's effective permissions, and the assistant's tools follow them. The role editor screen is the next step. | DECIDED (2026-10-03, delegated) |

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
