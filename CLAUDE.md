# CLAUDE.md — Business OS (codename)

Modular, multi-tenant Business OS + AI Workforce for small and medium businesses.
Israel first (Hebrew), then US/EU (American English). Industries are categories and sub-categories on equal footing (the fitness studio was the prototype).

## Working agreement

- **Conversation with the owner is in Hebrew.** Explain decisions clearly and simply; the owner is a
  senior data engineer but new to app/product development.
- **Everything in the codebase is in English**: identifiers, DB tables/columns, API fields, commits,
  code comments, technical docs. Hebrew appears only in translation resources (`he` locale files)
  and in user-entered content.
- Before a significant product/architecture decision, propose it and wait for the owner's answer.
  Record every decision in [`docs/DECISIONS.md`](docs/DECISIONS.md).
- Keep the project status current: with every merged pull request update [`docs/STATUS.md`](docs/STATUS.md)
  and its Hebrew twin [`docs/STATUS.he.md`](docs/STATUS.he.md) (for the owner), and the GitHub issues (labels `status: in progress` / `status: planned` / `status: needs decision`;
  pull requests close their issues).
- Build small, vertical slices end-to-end (DB → API → Web → Mobile). Every slice must keep tenant
  isolation, i18n/RTL, dark mode and accessibility intact.
- Never paste or commit secrets. Secrets live in environment variables / provider secret stores.

## Where things are

| Path | What |
|---|---|
| `apps/api` | Python API (FastAPI, Alembic migrations, tests) |
| `apps/web` | Next.js: marketing site, business web app, MyBiz console |
| `apps/client-app`, `apps/business-app`, `apps/staff-app` | Expo apps: the clients' app, the business app, the MyBiz team app |
| `packages/app-kit` | Shared screens, components and providers for the Expo apps |
| `packages/i18n` | Translations (`he`, `en`) and locale-aware formatting (money) |
| `packages/verticals` | The industry catalog (categories, sub-categories, packs) |
| `packages/api-client` | Typed API client generated from the API's OpenAPI schema |
| `supabase/` | Local Supabase config and auth email templates |
| `e2e/` | End-to-end checks (Playwright, Python) |
| `docs/spec/v1/` | Original owner spec (Hebrew + English .docx) |
| `docs/spec/v2/` | Detailed v2 chapters (architecture, data model, AI) |
| `docs/spec/v3/` | Current product spec (source of truth), English and Hebrew |
| `docs/proposals/`, `docs/reviews/` | Design proposals per feature; architecture reviews |
| `docs/DECISIONS.md` | Decision log |
| `docs/STATUS.md`, `docs/STATUS.he.md` | Project status board (done, in progress, next), English and Hebrew |
| `docs/verticals.md` | Industries: the category catalog and how to add a category |
| `docs/design-system.md` | Design tokens and where to change what (font, colors, buttons, texts, prices) |
| `docs/integrations.md` | Outside services behind swappable providers: how to add or switch one |

## Non-negotiable principles

1. **The backend is the authority, not the AI.** AI acts only through approved tools; sensitive
   actions become server-side Pending Actions, re-validated on confirmation.
2. **Tenant isolation**: every tenant-scoped row has `tenant_id`; enforced in the API and by Postgres RLS.
3. **i18n by design**: no hard-coded user-facing strings; RTL/LTR via logical CSS properties.
4. **Money** is stored as integer minor units + ISO currency code. **Time** is `timestamptz` (UTC)
   plus the tenant's IANA time zone for display.
5. **Usage is measurable**: every billable usage (AI, messages, storage) emits a usage event.
6. **Vertical-agnostic core**: vertical-specific behavior lives in vertical packs (config), not in
   `if vertical == ...` branches.
