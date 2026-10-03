# Spec v2 — Working Draft

Derived from the owner's Master Spec v1.1 ([`../v1/`](../v1/)) plus the decisions in
[`../../DECISIONS.md`](../../DECISIONS.md). v1 remains the vision document; v2 is the buildable spec.

| # | Document | Contents |
|---|---|---|
| 01 | [Product scope](01-product-scope.md) | Vision, sides of the platform, roles, what's in prototype / MVP |
| 02 | [Verticals](02-verticals.md) | Vertical-agnostic core and vertical packs |
| 03 | [Pricing & configurator](03-pricing-and-configurator.md) | Build-your-own plan, modules, meters, billing rules |
| 04 | [Architecture](04-architecture.md) | Stack, monorepo layout, tenancy, environments |
| 05 | [Data model](05-data-model.md) | Core entities and conventions (ERD) |
| 06 | [AI](06-ai.md) | LLM gateway, tools, pending actions, agents |
| 07 | [Roadmap](07-roadmap.md) | Phases and sprints |

## Changes from v1 (summary)

- Multi-vertical core from day one (fitness is the first pack, not the core model).
- Pricing presented as preset bundles + customize; minimum Core price; metered AI/messaging.
- Supabase used from day one (not "later") for Postgres, Auth and Storage.
- UI-prototype and working-prototype phases merged into vertical slices — no throwaway UI.
- One shared client app with dynamic branding instead of per-business apps.
- Added: Israeli specifics (health declaration, membership freeze, punch cards, standing orders,
  Israeli payment/invoicing providers), data import/migration, background jobs, usage metering,
  AI audit trail, prompt-injection handling, Privacy Protection Law Amendment 13 and IS 5568.
