# Project status

_Last updated: 2026-10-06_ · Updated with every merged pull request. Open work lives in
[GitHub issues](https://github.com/adiredri/business-os/issues); each phase is an `epic` issue
whose sub-issues show its progress. ([עברית](STATUS.he.md))

**Now:** the websites, in order: the marketing site, then the business web system (CRM); the apps after both are complete (decision X5).
**Next:** phase 7, the apps, and the architecture follow-ups ([#63](https://github.com/adiredri/business-os/issues/63)).

## Board

| Phase | What | Status | Tracking |
|---|---|---|---|
| Foundation | Core, schedule and appointments, clients, plans, client app, AI assistant (demo), reports, modules, billing, CRM leads, messaging, reviews, promo codes | ✅ Done | earlier PRs |
| Spec v3 | Phased plan, spec in Hebrew and English (Markdown and Word) | ✅ Done | #26 |
| 1 — Marketing website | Full site, sign-up journey (cart, summary, simulated payment), welcome email, getting started | ✅ Done | #27 |
| 2 — Business web app | Locked modules with previews and upsell, sales page, profiles, full review | ✅ Done | #28 |
| 3 — MyBiz console | Team levels and permissions, working inside a business, actions, support inbox, audit | ✅ Done | #29 |
| 4 — Apps | Business app and MyBiz team app built, shared app kit, client app polish, architecture review ([findings](reviews/architecture-2026-10.md)) | ✅ Done | #35 |
| 5 — Industries | Category → sub-category template in one catalog ([how to add one](verticals.md)); five main categories with 25 sub-categories; five more coming soon | ✅ Done | #30 |
| 6 — Businesses and branches | One owner with several businesses, each with several branches. Done: my businesses, business menu, current branch, data and numbers per branch, branches per team member, extra-branch charge follows branches. Demo generator for any industry with branches, and a staging workflow. Staging migrates before the API starts. Demo accounts on staging are ready and seeded | ✅ Done | #55 |
| 7 — More categories | Core capabilities that open the future categories | ⚪ Planned | #33 |
| Go-live | Real payments, invoicing, email, WhatsApp, AI key, hardening, store builds | ⚪ When the owner decides | #34 |

## In progress

- Business web system (CRM) polish. Round 1 done: clients list with plan and last visit, team avatars, reports heatmap. Round 2 done: plans show holders and recent sales, services show sessions and occupancy. Round 3 done: shorter client history, phone day strip on the schedule. Final pass done for the business app and the MyBiz console. Marketing site: structured data (product, price, questions) for search results, and the industry page's navs no longer share a name
- [#38](https://github.com/adiredri/business-os/issues/38) Owner review on computer and phone

## Next

- [#63](https://github.com/adiredri/business-os/issues/63) Architecture follow-ups: set-based queries, shared sign-in in the app kit, one money helper, more tests

## Planned

- Phase 7: [#41](https://github.com/adiredri/business-os/issues/41) resources (courts, rooms) ·
  [#42](https://github.com/adiredri/business-os/issues/42) on-site jobs ·
  [#43](https://github.com/adiredri/business-os/issues/43) dependents (pets, children) ·
  [#44](https://github.com/adiredri/business-os/issues/44) quotes, deposits and events ·
  [#45](https://github.com/adiredri/business-os/issues/45) documents and retainers
- Go-live: [#48](https://github.com/adiredri/business-os/issues/48) domain and email ·
  [#49](https://github.com/adiredri/business-os/issues/49) WhatsApp and SMS ·
  [#50](https://github.com/adiredri/business-os/issues/50) Claude API key ·
  [#51](https://github.com/adiredri/business-os/issues/51) hardening and store builds

## Waiting for the owner's decision

- [#46](https://github.com/adiredri/business-os/issues/46) Payment provider (O1)
- [#47](https://github.com/adiredri/business-os/issues/47) Invoicing provider (O2)
- [#36](https://github.com/adiredri/business-os/issues/36) Final brand name (O3)
- [#64](https://github.com/adiredri/business-os/issues/64) Does a team member's branch assignment restrict what they see?

## Health

- CI (lint, typecheck, tests, build) runs on every pull request; `main` is green.
- About 290 API tests and 28 end-to-end browser flows, including accessibility (WCAG AA) and dark mode.
- Paid services run in simulated mode until go-live (spec section 10).
