# Project status

_Last updated: 2026-10-05_ · Updated with every merged pull request. Open work lives in
[GitHub issues](https://github.com/adiredri/business-os/issues); each phase is an `epic` issue
whose sub-issues show its progress. ([עברית](STATUS.he.md))

**Now:** phase 6 — businesses and branches ([#55](https://github.com/adiredri/business-os/issues/55)): one owner, several businesses, each with several branches, and a full demo.
**Next:** the rest of phase 4 (client app polish, architecture review), then phase 7.

## Board

| Phase | What | Status | Tracking |
|---|---|---|---|
| Foundation | Core, schedule and appointments, clients, plans, client app, AI assistant (demo), reports, modules, billing, CRM leads, messaging, reviews, promo codes | ✅ Done | earlier PRs |
| Spec v3 | Phased plan, spec in Hebrew and English (Markdown and Word) | ✅ Done | #26 |
| 1 — Marketing website | Full site, sign-up journey (cart, summary, simulated payment), welcome email, getting started | ✅ Done | #27 |
| 2 — Business web app | Locked modules with previews and upsell, sales page, profiles, full review | ✅ Done | #28 |
| 3 — MyBiz console | Team levels and permissions, working inside a business, actions, support inbox, audit | ✅ Done | #29 |
| 4 — Apps | Business app and MyBiz team app built, shared app kit | 🟡 Mostly done | #35 |
| 5 — Industries | Category → sub-category template in one catalog ([how to add one](verticals.md)); five main categories with 25 sub-categories; five more coming soon | ✅ Done | #30 |
| 6 — Businesses and branches | One owner with several businesses, each with several branches. Done: my businesses, business menu, current branch, data and numbers per branch, branches per team member, extra-branch charge follows branches. Demo generator for any industry with branches, and a staging workflow. Left: running the owner's demo once the accounts sign up | 🟡 Almost done | #55 |
| 7 — More categories | Core capabilities that open the future categories | ⚪ Planned | #33 |
| Go-live | Real payments, invoicing, email, WhatsApp, AI key, hardening, store builds | ⚪ When the owner decides | #34 |

## In progress

- Owner's demo on staging: waiting for adired7399@gmail.com to sign up, then the seed workflow runs ([#58](https://github.com/adiredri/business-os/issues/58))
- [#38](https://github.com/adiredri/business-os/issues/38) Owner review on computer and phone

## Next

- [#39](https://github.com/adiredri/business-os/issues/39) Client app: final polish
- [#40](https://github.com/adiredri/business-os/issues/40) Architecture review after phase 4

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

## Health

- CI (lint, typecheck, tests, build) runs on every pull request; `main` is green.
- About 280 API tests and 27 end-to-end browser flows, including accessibility (WCAG AA) and dark mode.
- Paid services run in simulated mode until go-live (spec section 10).
