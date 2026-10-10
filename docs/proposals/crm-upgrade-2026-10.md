# Business workspace upgrade (October 2026): gap analysis and plan

The owner's 16-section requirements list (project thread, 2026-10-10) asks to take the business
web app (the "CRM") and the site from "70–80% there" to a premium business operating system.
This document maps each section to what already exists, lists the gaps, and orders the work in
phases. Every phase ships as small pull requests that keep tenant isolation, i18n/RTL, dark mode
and accessibility intact. Choices made without the owner (he asked for work to continue
overnight) are marked **Default** and recorded in `docs/DECISIONS.md` (X23 onward); each can be
revisited.

## How the system is shaped today (what we build on)

- **Identity**: every person has their own Supabase account → `app.users` (name, email, locale).
  A business is a tenant (`app.tenants`); people join it through `app.tenant_members`
  (role owner / manager / staff / front_desk, optional custom role, `location_ids` branches).
  One person can already belong to many businesses, and the business menu switches between them.
  MyBiz staff have separate platform permissions (`app.platform_staff`). Clients of a business
  are `app.clients` and only reach the client app, never the business system.
- **Network and branches**: a "network" in the owner's words is one business (tenant) with
  several branches (`app.locations`). The current branch is a cookie per business, sent as
  `X-Location-Id`; Postgres filters through `app.in_branch()`, and staff assigned to branches see
  only theirs (X19).
- **Scheduling**: sessions (classes, appointments, room reservations) with branch and room;
  `staff_hours` (weekly availability for appointments), `staff_time_off`, business-wide
  `closed_days`, `room_hours`. No employee shifts and no branch opening hours.
- **Files**: the business logo is stored in Postgres (`bytea`, ≤ 512 KB, type sniffed from the
  bytes) and served by a public function; client documents go through the storage provider.
- **Look**: design tokens in `apps/web/src/app/globals.css`, light / dark / system through
  next-themes, a business's brand color replaces `--primary` inside its area.

## Gap analysis

| # | Section | Exists | Gap → plan |
|---|---|---|---|
| 1 | Personal profiles | Personal accounts, multi-business membership, `/account` with name and password, initials avatar | Profile picture (upload / replace / remove), phone, avatars everywhere (menu, team, roster), profile link in the header menu |
| 2 | Business ID | Free-text `tax_id` on the MyBiz billing details only | Legal entity type + validated identifier on the business (Israeli check digit for ח.פ. / עוסק מורשה / עמותה; free format for other countries); visible only to owners and managers |
| 3 | Live data | Server actions revalidate the page after own changes | Refresh shared screens (calendar, dashboard, shifts) when the tab returns to focus and every minute while visible; pending/success/error states on forms |
| 4 | Employee scheduling | Weekly availability per person, time off | Shifts (per person, branch, date, time, role note), week board by person/branch, overlap detection, copy week; branch opening hours with breaks; one-person businesses get the simple "opening hours and availability" view instead of a shift board |
| 5 | Org hierarchy | — | `job_title` and `reports_to` per membership (no cycles), a collapsible org chart with avatars, titles and branches; reporting never changes permissions |
| 6 | Business / branch selector | `<details>` menu for businesses + a native `<select>` for branches | One popover: networks with their branches nested, search when long, keyboard and click-outside, no clipping, RTL, animated |
| 7 | Multi-branch | One current branch or "all" | Branch comparison report (revenue, sessions, attendance, new clients, appointments) and a multi-branch calendar filter with branch colors; never beyond the person's branches |
| 8 | Calendar | Week as seven columns of cards | Day and week time grid with a live "now" line, today highlighted, scroll to the current hour, shifts and closed periods drawn differently from sessions |
| 9 | Workspace images | Logo, brand color | A cover image for the business (dashboard header, menu) with a tasteful default |
| 10 | Themes | Light / dark / system, indigo accent | Three palettes: **MyBiz** (black, white, deep purple — default), **Ocean**, **Forest**; per person, remembered; contrast checked in both modes |
| 11 | Buttons, navigation | `btn-primary` / `btn-secondary`, side menu | Lighter, consistent button sizes; a submit button with spinner and double-submit guard; a back link / breadcrumb on detail pages; dropdowns per section 6 |
| 12 | Performance | Server components, a `loading.tsx` for the business area | Measure each navigation; remove sequential API round trips in the layout; skeletons per page; prefetch |
| 13 | Demo data | Demos per industry (studio, club, pets, jobs, events, office, owner, platform) | Shifts, opening hours, hierarchy, titles, cover images in every demo |
| 14 | Multi-network demo owner | "owner" demo: pilates chain (5 branches) + barbershop (3) | New `networks` demo: Urban Slice (pizza, 4 branches), Pulse Fitness (2), Studio Bloom (3) for one owner; adds a Food & Restaurants category to the catalog |
| 15 | A11y, i18n | Hebrew/English, RTL, dark mode, focus rings | Kept on every new screen; reduced motion respected by every new animation |

## Defaults chosen (owner can change any of them)

- **Network = business, branch = location.** No new "network" layer: the demo owner owns three
  businesses, each with its branches. The portfolio view is the existing "my businesses" page,
  extended with per-business numbers.
- **Profile pictures stay in Postgres like the logo** (≤ 512 KB, PNG/JPEG/WebP, type checked by
  content). They are served only to signed-in people who share a business with that person (or
  the person themself), through the web app, never as public URLs.
- **Business identifier**: `legal_entity_type` (`company`, `licensed_dealer`, `exempt_dealer`,
  `nonprofit`, `partnership`, `other`) and `business_number`, validated with the Israeli
  9-digit check digit for Israeli entity types. Shown and editable only with the settings
  permission; never in client-facing pages.
- **Live updates without Supabase Realtime for now.** The database is reached through the API's
  own connection and row-level security reads `app.*` settings, not Supabase JWT claims, so
  Realtime subscriptions would need a second security model. Instead shared screens refresh on
  focus and every 60 seconds while visible; revisit when two people editing the same calendar
  becomes common.
- **Shifts reject overlaps for the same person** (the API answers 409 naming the clash), and
  warn (not block) when a shift falls on that person's time off or outside branch hours.
- **Hierarchy is per business**: `reports_to` points at another member of the same business;
  cycles are refused by the database.
- **Themes are personal** (each person picks), saved on the account and in a cookie so the page
  renders in the right colors with no flash. A business's own brand color, when set, still
  colors its area.
- **No expense records exist**, so the branch comparison shows revenue and operations only; an
  expenses module is listed as follow-up rather than invented.
- **Mobile apps** keep working unchanged; avatars, shifts and the org chart reach them in a later
  slice (the API is shared, so the data is ready for them).

## Phases and pull requests

1. **Architecture and data model** — migration 0057: avatars and phone on users; job title and
   reports-to on memberships; legal entity and business number on tenants; branch opening hours;
   shifts. API endpoints with permissions and tenant-isolation tests.
2. **Core functionality** — profile page with picture; business ID in settings and sign-up;
   opening hours per branch; shift board; org chart; branch comparison report; time-grid calendar
   with the now line and multi-branch filter; cover image.
3. **UI/UX** — the network/branch popover; header profile menu; buttons and submit states; back
   links; the three palettes; workspace cover.
4. **Performance** — measure, parallelize the layout's API calls, skeletons, prefetch.
5. **Demo and validation** — demo data for all of the above; the `networks` demo owner; e2e checks
   for the new screens; STATUS and DECISIONS updated.

## Progress

Kept current as pull requests merge; see `docs/STATUS.md`.
