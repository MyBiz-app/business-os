# Project status

_Last updated: 2026-10-06_ · Updated with every merged pull request. Open work lives in
[GitHub issues](https://github.com/adiredri/business-os/issues); each phase is an `epic` issue
whose sub-issues show its progress. ([עברית](STATUS.he.md))

**Now:** the apps' second round is merged (#85): the business app runs the whole day from the phone, the MyBiz team app has business and request cards. Phase 7: resources (#41) are done and opened Sports & facilities; dependents (#43, decision X10) are done and opened Pet services. Also waiting: sign-up emails on staging (#48) and the open decisions below.
**Next:** on-site jobs (#42), then quotes and deposits (#44), documents and retainers (#45).

## Board

| Phase | What | Status | Tracking |
|---|---|---|---|
| Foundation | Core, schedule and appointments, clients, plans, client app, AI assistant (demo), reports, modules, billing, CRM leads, messaging, reviews, promo codes | ✅ Done | earlier PRs |
| Spec v3 | Phased plan, spec in Hebrew and English (Markdown and Word) | ✅ Done | #26 |
| 1 — Marketing website | Full site, sign-up journey (cart, summary, simulated payment), welcome email, getting started | ✅ Done | #27 |
| 2 — Business web app | Locked modules with previews and upsell, sales page, profiles, full review | ✅ Done | #28 |
| 3 — MyBiz console | Team levels and permissions, working inside a business, actions, support inbox, audit | ✅ Done | #29 |
| 4 — Apps | Business app and MyBiz team app built, shared app kit, client app polish, architecture review ([findings](reviews/architecture-2026-10.md)). Second round: the business app runs the whole day (#84) | 🟡 In progress | #35 |
| 5 — Industries | Category → sub-category template in one catalog ([how to add one](verticals.md)); five main categories with 25 sub-categories; five more coming soon | ✅ Done | #30 |
| 6 — Businesses and branches | One owner with several businesses, each with several branches. Done: my businesses, business menu, current branch, data and numbers per branch, branches per team member, extra-branch charge follows branches. Demo generator for any industry with branches, and a staging workflow. Staging migrates before the API starts. Demo accounts on staging are ready and seeded | ✅ Done | #55 |
| 7 — More categories | Core capabilities that open the future categories. Done: courts and rooms by the hour (#41), which opened Sports & facilities; pets and children under a client (#43), which opened Pet services | 🟡 In progress | #33 |
| Go-live | Real payments, invoicing, email, WhatsApp, AI key, hardening, store builds | ⚪ When the owner decides | #34 |

## In progress

- ✅ [#43](https://github.com/MyBiz-app/business-os/issues/43) Dependents: pets and children (X10, [proposal](proposals/43-dependents.md)). Slice 1 done: a client can have pets or children (which kind, and the extra details asked about each, come from the industry pack); staff and the client in the app add and edit them; a booking can be for one of them, so one owner can bring two dogs to the same session; rosters and visit histories show who comes; an industry can require choosing one on every booking. Slice 2 done (web): the client card has the client's pets or children (add, edit, "no longer comes") with the industry's details about each; booking into a class or an appointment picks which one comes; rosters show "Rex · Dana Levi". Slice 3 done: in the client app, "My pets" / "My children" in the profile, and booking a class or an appointment asks who's coming (a client can bring two dogs to the same session); in the business app, the client card lists them and booking someone into a session picks which one; the AI assistant books for a pet. Slice 4 done: **Pet services is open (beta)** with pet grooming, dog training and doggy day care: an owner's pets with species, breed, size, weight, temperament, vaccinations and allergies, and every booking names the pet; Kids activities now keeps a profile per child. The demo generator has a grooming salon (`--demo pets`) with owners and their pets. Checked end to end with `e2e/pets.py` (web) and `e2e/pets_app.py` (client app).
- ✅ [#41](https://github.com/MyBiz-app/business-os/issues/41) Resources: courts and rooms by the hour (X9). Slice 1 done: rooms can be bookable with their own hours, resource services have a price per hour and lengths, free times per court and length, reservations by staff and by clients (no plan used), and the database refuses a double booking even when two people book at once. Slice 2 done (web): a room can be marked "for rent by the hour" with its opening hours, a service "a court or room by the hour" with price per hour, lengths and its courts, and a "Courts & rooms" page with the day as a grid (courts × hours) and new reservations by the front desk. Slice 3 done: clients book a court in the app (what, how long, day, court and time) and pay in the app (simulated) with a receipt; a business may instead be paid at the venue, where the front desk records the payment. Slice 4 done: the business app reserves a court for a client and takes the payment; the reports show each court's hours reserved of hours open, reservations and revenue; the AI assistant can find free courts. Slice 5 done: **Sports & facilities is open (beta)** with padel & tennis clubs, football pitches, rehearsal studios and meeting rooms; a new business starts with its courts ready to book; the demo generator has a padel club (`--demo club`) with a month and a half of reservations.
- ✅ [#84](https://github.com/MyBiz-app/business-os/issues/84) (merged in #85) Business app: the whole day from the phone: today with a day strip for the week and what needs attention; a session with check-in, booking someone in, cancelling and a visit note; clients with filters, a new client, and a full client card (plans and selling one, what's coming up, recent visits, notes, a WhatsApp message); a leads tab by stage with a lead card (call, move the stage, log a call, turn into a client) and a new lead; the messages sent. Shared building blocks in the app kit (back link, list rows, avatars, badges, pill rows). The demo generator now also writes a month of sent messages. Checked end to end with `e2e/business_app.py` in Hebrew/light and English/dark, with no accessibility issues.
- MyBiz team app, second round: a home with the platform's numbers, this month's billing, open requests and new businesses; businesses with sorting and a business card (numbers, modules, invoices, more trial days); a request card (call, write back, take it, status, internal notes). Checked end to end with `e2e/staff_app.py`.
- Websites complete. Polished in four rounds: the clients list shows each client's plan and last visit, team avatars, a busy-hours heatmap and occupancy bars in the reports, plans and services show how they are used, a shorter client history, a day strip on the phone schedule, a two-row header on phones, search, sort and pages in the MyBiz console, a billing summary, and structured data for search results.
- Checked end to end: `dod.py` (sign-up through the AI assistant and the console), a crawl of every page in Hebrew and English on computer and phone with no errors, no accessibility violations and nothing spilling off the screen, in light and dark mode.
- [#38](https://github.com/adiredri/business-os/issues/38) Owner review on computer and phone

## Next

- Client app: the same pass (shared building blocks, fuller screens, end-to-end checks)

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
- About 330 API tests and 31 end-to-end browser flows, including accessibility (WCAG AA) and dark mode; the business app flow covers 7 steps on a phone.
- Paid services run in simulated mode until go-live (spec section 10).
